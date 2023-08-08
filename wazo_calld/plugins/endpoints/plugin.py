# Copyright 2019-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_confd_client import Client as ConfdClient
from xivo.pubsub import CallbackCollector
from xivo.status import Status

from .bus import EventHandler
from .http import LineEndpoints, TrunkEndpoints
from .services import ConfdCache, EndpointsService, NotifyingStatusCache
from .notifier import EndpointStatusNotifier


class Plugin:
    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        config = dependencies['config']
        status_aggregator = dependencies['status_aggregator']
        token_changed_subscribe = dependencies['token_changed_subscribe']
        bus_consumer = dependencies['bus_consumer']
        bus_publisher = dependencies['bus_publisher']

        confd_client = ConfdClient(**config['confd'])
        token_changed_subscribe(confd_client.set_token)

        confd_cache = ConfdCache(confd_client)
        notifier = EndpointStatusNotifier(bus_publisher, confd_cache)

        status_cache = NotifyingStatusCache(notifier.endpoint_updated, ari.client)
        endpoints_service = EndpointsService(confd_cache, status_cache)

        self._async_tasks_completed = False
        startup_callback_collector = CallbackCollector()
        ari.client_initialized_subscribe(startup_callback_collector.new_source())
        startup_callback_collector.subscribe(status_cache.initialize)
        startup_callback_collector.subscribe(self._set_async_tasks_completed)

        event_handler = EventHandler(status_cache, confd_cache)
        event_handler.subscribe(bus_consumer)

        status_aggregator.add_provider(self._provide_status)

        api.add_resource(
            TrunkEndpoints,
            '/trunks',
            resource_class_args=[
                endpoints_service,
            ],
        )

        api.add_resource(
            LineEndpoints,
            '/lines',
            resource_class_args=[
                endpoints_service,
            ],
        )

    def _set_async_tasks_completed(self):
        self._async_tasks_completed = True

    def _provide_status(self, status):
        value = Status.ok if self._async_tasks_completed else Status.fail
        status['plugins']['endpoints']['status'] = value
