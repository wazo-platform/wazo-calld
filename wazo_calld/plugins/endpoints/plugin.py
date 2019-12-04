# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_confd_client import Client as ConfdClient

from .bus import EventHandler
from .resources import TrunkEndpoints
from .services import ConfdCache, EndpointsService, NotifyingStatusCache
from .notifier import EndpointStatusNotifier


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']
        bus_consumer = dependencies['bus_consumer']
        bus_publisher = dependencies['bus_publisher']

        confd_client = ConfdClient(**config['confd'])
        token_changed_subscribe(confd_client.set_token)

        confd_cache = ConfdCache(confd_client)
        notifier = EndpointStatusNotifier(bus_publisher, confd_cache)

        status_cache = NotifyingStatusCache(notifier.endpoint_updated, ari.client)
        endpoints_service = EndpointsService(confd_client, ari.client, status_cache)

        event_handler = EventHandler(status_cache, confd_cache)
        event_handler.subscribe(bus_consumer)

        api.add_resource(
            TrunkEndpoints,
            '/trunks',
            resource_class_args=[
                endpoints_service,
            ],
        )
