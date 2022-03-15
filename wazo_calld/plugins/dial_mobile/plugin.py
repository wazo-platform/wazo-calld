# Copyright 2019-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_amid_client import Client as AmidClient
from xivo.pubsub import CallbackCollector

from .stasis import DialMobileStasis
from .services import DialMobileService
from .bus_consume import EventHandler


class Plugin:

    def load(self, dependencies):
        ari = dependencies['ari']
        pubsub = dependencies['pubsub']
        bus_consumer = dependencies['bus_consumer']
        token_changed_subscribe = dependencies['token_changed_subscribe']
        config = dependencies['config']

        amid_client = AmidClient(**config['amid'])
        token_changed_subscribe(amid_client.set_token)

        service = DialMobileService(ari, amid_client)
        pubsub.subscribe('stopping', lambda _: service.on_calld_stopping())

        stasis = DialMobileStasis(ari, service)

        startup_callback_collector = CallbackCollector()
        ari.client_initialized_subscribe(startup_callback_collector.new_source())
        startup_callback_collector.subscribe(stasis.initialize)

        event_handler = EventHandler(service)
        event_handler.subscribe(bus_consumer)
