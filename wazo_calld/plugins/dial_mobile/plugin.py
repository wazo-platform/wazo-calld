# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from wazo_amid_client import Client as AmidClient
from wazo_auth_client import Client as AuthClient
from wazo_confd_client import Client as ConfdClient
from xivo.pubsub import CallbackCollector

from wazo_calld.bus import CoreBusPublisher
from wazo_calld.types import PluginDependencies

from .bus_consume import EventHandler
from .notifier import Notifier
from .services import (
    DEFAULT_PSTN_FALLBACK_MIN_TIMEOUT,
    DEFAULT_PSTN_FALLBACK_RING_TIMEOUT_FACTOR,
    DialMobileService,
)
from .stasis import DialMobileStasis


class Plugin:
    def load(self, dependencies: PluginDependencies) -> None:
        ari = dependencies['ari']
        pubsub = dependencies['pubsub']
        bus_consumer = dependencies['bus_consumer']
        token_changed_subscribe = dependencies['token_changed_subscribe']
        config = dependencies['config']

        # Mobile push/cancel notifications are published on a DEDICATED bus
        # publisher (its own AMQP connection) rather than the shared
        # dependencies['bus_publisher']. RabbitMQ applies flow-control per
        # connection: calld's shared publisher carries calld's whole outbound
        # event stream, and when the broker throttles that connection every
        # publish on it stalls -- including the incoming-call push, which then
        # reaches the mobile tens of seconds late (phantom call) or not at all
        # (missed call). A dedicated connection carrying only the low-rate
        # push/cancel traffic is not flow-controlled, so pushes go out promptly.
        #
        # Like the shared publisher built in controller.py, this is a non-threaded
        # BusPublisher: it connects lazily on first publish and has no start()/stop()
        # lifecycle to manage. Argument order mirrors controller.py:
        # from_config(service_uuid, bus_config).
        push_bus_publisher = CoreBusPublisher.from_config(config['uuid'], config['bus'])

        amid_client = AmidClient(**config['amid'])
        token_changed_subscribe(amid_client.set_token)

        auth_client = AuthClient(**config['auth'])
        token_changed_subscribe(auth_client.set_token)

        confd_client = ConfdClient(**config['confd'])
        token_changed_subscribe(confd_client.set_token)

        pstn_fallback_config = config.get('dial_mobile', {}).get('pstn_fallback', {})
        notifier = Notifier(push_bus_publisher)
        service = DialMobileService(
            ari,
            notifier,
            amid_client,
            auth_client,
            confd_client,
            pstn_fallback_min_timeout=pstn_fallback_config.get(
                'min_timeout', DEFAULT_PSTN_FALLBACK_MIN_TIMEOUT
            ),
            pstn_fallback_ring_timeout_factor=pstn_fallback_config.get(
                'ring_timeout_factor', DEFAULT_PSTN_FALLBACK_RING_TIMEOUT_FACTOR
            ),
        )
        stasis = DialMobileStasis(ari, service)
        event_handler = EventHandler(service)

        event_handler.subscribe(bus_consumer)
        pubsub.subscribe('stopping', lambda _: service.on_calld_stopping())
        startup_callback_collector = CallbackCollector()
        ari.client_initialized_subscribe(startup_callback_collector.new_source())
        startup_callback_collector.subscribe(stasis.initialize)
