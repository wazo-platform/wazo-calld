# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Setup/teardown for the ARI connection-pool exhaustion load test.

Programs the mock wazo-auth with a user token and maintains a pool of real
chan-test channels (kept Up, owned by that user). These channels serve two
purposes simultaneously:

- they make ``GET /users/me/calls`` amplify into many ARI calls (one
  ``make_call_from_channel`` per owned channel), and
- they are referenced by the synthetic ``dial`` StasisStart events, so each
  spawned ``_PollingContactDialer`` thread keeps polling ARI (its ``channels.get``
  on a real channel succeeds instead of raising ``ARINotFound``).

Under load the chan-test channels get hung up faster than a fixed pool can
absorb, which kills the polling dialers and caps in-flight ARI calls below the
pool size. A background ``_ChannelKeeper`` therefore keeps the pool alive
(prunes dead ids, replenishes) and grows it over time so the number of
*sustained* dialers — and thus concurrent ARI calls — keeps climbing until the
pool-full condition appears.
"""
from __future__ import annotations

import logging
import os
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any

import ari
import requests
from ari.exceptions import ARINotFound, ARINotInStasis
from wazo_test_helpers import until
from wazo_test_helpers.auth import AuthClient, MockUserToken

logger = logging.getLogger(__name__)

# Mirrors integration_tests/suite/helpers/constants.py
ENDPOINT_AUTOANSWER = 'Test/integration-caller/autoanswer'
STASIS_APP = 'callcontrol'
STASIS_APP_INSTANCE = 'load-test'

# Errors a transient ARI operation may raise without meaning the run is broken.
_TRANSIENT_ARI_ERRORS = (requests.RequestException, ARINotFound, ARINotInStasis)


@dataclass
class LoadTestConfig:
    ari_url: str
    ari_username: str
    ari_password: str
    auth_host: str
    auth_port: int
    token: str
    user_uuid: str
    tenant_uuid: str
    channel_count: int
    channel_cap: int
    channel_growth_step: int
    channel_growth_interval: float
    keeper_interval: float
    keeper_batch: int

    @classmethod
    def from_env(cls) -> LoadTestConfig:
        return cls(
            ari_url=os.environ['ARI_URL'],
            ari_username=os.environ.get('ARI_USERNAME', 'xivo'),
            ari_password=os.environ.get('ARI_PASSWORD', 'xivo'),
            auth_host=os.environ.get('AUTH_HOST', '127.0.0.1'),
            auth_port=int(os.environ['AUTH_PORT']),
            token=os.environ.get('CALLD_TOKEN', 'load-test-token'),
            user_uuid=os.environ.get(
                'CALLD_USER_UUID', 'load0000-0000-0000-0000-000000000001'
            ),
            tenant_uuid=os.environ.get(
                'CALLD_TENANT_UUID', 'ffffffff-ffff-ffff-ffff-ffffffffffff'
            ),
            channel_count=int(os.environ.get('CHANNEL_COUNT', '20')),
            channel_cap=int(os.environ.get('CHANNEL_CAP', '200')),
            channel_growth_step=int(os.environ.get('CHANNEL_GROWTH_STEP', '15')),
            channel_growth_interval=float(
                os.environ.get('CHANNEL_GROWTH_INTERVAL', '5')
            ),
            keeper_interval=float(os.environ.get('CHANNEL_KEEPER_INTERVAL', '2')),
            keeper_batch=int(os.environ.get('CHANNEL_KEEPER_BATCH', '25')),
        )


@dataclass
class SharedState:
    channel_ids: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _ari: Any = None
    _keeper: _ChannelKeeper | None = None

    def set_channels(self, ari_client, channel_ids: list[str]) -> None:
        with self._lock:
            self._ari = ari_client
            self.channel_ids = list(channel_ids)

    def add(self, channel_ids: list[str]) -> None:
        with self._lock:
            self.channel_ids.extend(channel_ids)

    def prune(self, live: set[str]) -> int:
        with self._lock:
            before = len(self.channel_ids)
            self.channel_ids = [c for c in self.channel_ids if c in live]
            return before - len(self.channel_ids)

    def count(self) -> int:
        with self._lock:
            return len(self.channel_ids)

    def random_channel(self) -> str | None:
        with self._lock:
            if not self.channel_ids:
                return None
            return random.choice(self.channel_ids)

    def teardown(self) -> None:
        with self._lock:
            ari_client = self._ari
            channel_ids = list(self.channel_ids)
            self.channel_ids = []
            self._ari = None
        if ari_client is None:
            return
        for channel_id in channel_ids:
            try:
                ari_client.channels.hangup(channelId=channel_id)
            except ARINotFound:
                continue


SHARED = SharedState()


def _program_auth_token(config: LoadTestConfig) -> None:
    auth = AuthClient(config.auth_host, config.auth_port)
    token = MockUserToken(
        config.token,
        config.user_uuid,
        metadata={'uuid': config.user_uuid, 'tenant_uuid': config.tenant_uuid},
    )
    auth.set_token(token)
    logger.info(
        'Programmed mock auth token %s -> user %s', config.token, config.user_uuid
    )


def _originate_owned_channel(ari_client, config: LoadTestConfig) -> str:
    channel = ari_client.channels.originate(
        endpoint=ENDPOINT_AUTOANSWER,
        app=STASIS_APP,
        appArgs=[STASIS_APP_INSTANCE],
    )

    def in_stasis() -> bool:
        try:
            ari_client.channels.setChannelVar(
                channelId=channel.id, variable='TEST_STASIS', value=''
            )
            return True
        except ARINotInStasis:
            return False

    until.true(in_stasis, tries=5)
    channel.setChannelVar(variable='WAZO_USERUUID', value=config.user_uuid)
    channel.setChannelVar(variable='WAZO_TENANT_UUID', value=config.tenant_uuid)
    return channel.id


class _ChannelKeeper:
    """Keeps the owned-channel pool alive and growing during the run.

    Each iteration: prune ids whose channel is gone, then originate channels up
    to a target that grows linearly with elapsed time (capped). Sustained
    polling dialers scale with the number of live channels, so growing the pool
    drives concurrent ARI calls past the pool size.
    """

    def __init__(self, ari_client, config: LoadTestConfig, shared: SharedState):
        self._ari = ari_client
        self._config = config
        self._shared = shared
        self._stop = threading.Event()
        self._thread = threading.Thread(
            name='ChannelKeeper', target=self._run, daemon=True
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=15)

    def _run(self) -> None:
        start = time.monotonic()
        while not self._stop.wait(self._config.keeper_interval):
            try:
                self._reconcile(start)
            except _TRANSIENT_ARI_ERRORS:
                logger.exception('channel keeper iteration failed')

    def _target(self, elapsed: float) -> int:
        grown = self._config.channel_count + (
            int(elapsed // self._config.channel_growth_interval)
            * self._config.channel_growth_step
        )
        return min(self._config.channel_cap, grown)

    def _reconcile(self, start: float) -> None:
        live = {channel.id for channel in self._ari.channels.list()}
        pruned = self._shared.prune(live)

        target = self._target(time.monotonic() - start)
        to_create = min(
            self._config.keeper_batch, max(0, target - self._shared.count())
        )
        created: list[str] = []
        for _ in range(to_create):
            if self._stop.is_set():
                break
            try:
                created.append(_originate_owned_channel(self._ari, self._config))
            except _TRANSIENT_ARI_ERRORS:
                logger.exception('keeper failed to originate a channel')
                break
        if created:
            self._shared.add(created)
        if pruned or created:
            logger.info(
                'keeper: pruned %d dead, created %d, pool=%d (target=%d)',
                pruned,
                len(created),
                self._shared.count(),
                target,
            )


def setup(config: LoadTestConfig | None = None) -> LoadTestConfig:
    config = config or LoadTestConfig.from_env()
    _program_auth_token(config)

    ari_client = ari.connect(
        base_url=config.ari_url,
        username=config.ari_username,
        password=config.ari_password,
    )

    channel_ids = [
        _originate_owned_channel(ari_client, config)
        for _ in range(config.channel_count)
    ]
    SHARED.set_channels(ari_client, channel_ids)
    logger.info('Created %d owned channels for the load test', len(channel_ids))

    keeper = _ChannelKeeper(ari_client, config, SHARED)
    SHARED._keeper = keeper
    keeper.start()
    logger.info(
        'Started channel keeper (cap=%d, +%d/%.0fs)',
        config.channel_cap,
        config.channel_growth_step,
        config.channel_growth_interval,
    )
    return config


def teardown() -> None:
    keeper = SHARED._keeper
    SHARED._keeper = None
    if keeper is not None:
        keeper.stop()
    SHARED.teardown()
    logger.info('Stopped channel keeper and hung up load-test channels')
