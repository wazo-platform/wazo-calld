# Copyright 2019-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from wazo_amid_client import Client as AmidClient
from wazo_auth_client import Client as AuthClient
from xivo.pubsub import CallbackCollector

from wazo_calld.types import PluginDependencies

from .bus_consume import EventHandler
from .notifier import Notifier
from .services import DialMobileService
from .stasis import DialMobileStasis


class Plugin:
    def load(self, dependencies: PluginDependencies) -> None:
        ari = dependencies['ari']
        pubsub = dependencies['pubsub']
        bus_consumer = dependencies['bus_consumer']
        token_changed_subscribe = dependencies['token_changed_subscribe']
        config = dependencies['config']
        bus_publisher = dependencies['bus_publisher']

        amid_client = AmidClient(**config['amid'])
        token_changed_subscribe(amid_client.set_token)

        auth_client = AuthClient(**config['auth'])
        token_changed_subscribe(auth_client.set_token)

        notifier = Notifier(bus_publisher)
        service = DialMobileService(ari, notifier, amid_client, auth_client)
        stasis = DialMobileStasis(ari, service)
        event_handler = EventHandler(service)

        event_handler.subscribe(bus_consumer)
        pubsub.subscribe('stopping', lambda _: service.on_calld_stopping())
        startup_callback_collector = CallbackCollector()
        ari.client_initialized_subscribe(startup_callback_collector.new_source())
        startup_callback_collector.subscribe(stasis.initialize)
