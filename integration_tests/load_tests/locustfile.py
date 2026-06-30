# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Locust load test reproducing ARI client connection-pool exhaustion.

Two concurrent load sources contend for wazo-calld's single shared ARI
``requests.Session`` (default ``pool_maxsize=10``, ``pool_block=False``):

- ``CallsReader`` spams ``GET /users/me/calls`` via wazo-calld-client. Each
  request amplifies into many sequential ARI calls (one per owned channel).
- ``DialMobileFlooder`` publishes synthetic ``dial`` StasisStart events; each
  spawns an unbounded ``_PollingContactDialer`` thread polling ARI ~8x/s.

When in-flight ARI calls exceed 10, urllib3 logs
``Connection pool is full, discarding connection`` and ARI/HTTP latency climbs.
Watch the wazo-calld logs for that line; watch Locust for rising
``users/me/calls`` response times.
"""

from __future__ import annotations

import logging
import os
import time

import requests
from dial_events import DialMobileEventPublisher
from harness import SHARED, setup, teardown
from locust import User, between, events, task
from wazo_calld_client import Client as CalldClient

logger = logging.getLogger(__name__)

CALLD_HOST = os.environ.get('CALLD_HOST', '127.0.0.1')
CALLD_PORT = int(os.environ.get('CALLD_PORT', '9500'))
CALLD_TOKEN = os.environ.get('CALLD_TOKEN', 'load-test-token')
RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', '127.0.0.1')
RABBITMQ_PORT = int(os.environ.get('RABBITMQ_PORT', '5672'))
DIAL_AOR = os.environ.get('DIAL_AOR', 'load-test-aor')


@events.test_start.add_listener
def _on_test_start(environment, **kwargs):
    setup()


@events.test_stop.add_listener
def _on_test_stop(environment, **kwargs):
    teardown()


class CallsReader(User):
    """Spams GET /users/me/calls (the ARI-amplifying HTTP endpoint)."""

    weight = 10
    wait_time = between(0, 0.05)

    def on_start(self):
        self._calld = CalldClient(
            CALLD_HOST,
            CALLD_PORT,
            prefix=None,
            https=False,
            token=CALLD_TOKEN,
        )

    @task
    def list_my_calls(self):
        start = time.monotonic()
        exception = None
        length = 0
        try:
            result = self._calld.calls.list_calls_from_user()
            length = len(result.get('items', []))
        except requests.RequestException as e:
            exception = e
        elapsed_ms = (time.monotonic() - start) * 1000
        self.environment.events.request.fire(
            request_type='GET',
            name='users/me/calls',
            response_time=elapsed_ms,
            response_length=length,
            exception=exception,
        )


class DialMobileFlooder(User):
    """Publishes synthetic dial events, accruing dial_mobile polling threads."""

    weight = 1
    wait_time = between(0.2, 0.5)

    def on_start(self):
        self._publisher = DialMobileEventPublisher(RABBITMQ_HOST, RABBITMQ_PORT)

    @task
    def spawn_dialer(self):
        channel_id = SHARED.random_channel()
        if channel_id is None:
            return
        start = time.monotonic()
        exception = None
        try:
            self._publisher.publish_dial(channel_id, DIAL_AOR)
        except Exception as e:  # noqa: BLE001 - report any publish failure to Locust
            exception = e
        elapsed_ms = (time.monotonic() - start) * 1000
        self.environment.events.request.fire(
            request_type='AMQP',
            name='stasis dial event',
            response_time=elapsed_ms,
            response_length=0,
            exception=exception,
        )
