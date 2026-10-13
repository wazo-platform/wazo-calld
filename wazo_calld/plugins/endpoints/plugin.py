# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from wazo_confd_client import Client as ConfdClient
from xivo.pubsub import CallbackCollector
from xivo.status import Status

from wazo_calld.types import PluginDependencies, StatusDict

from .bus import EventHandler
from .http import LineEndpoints, TrunkEndpoints
from .notifier import EndpointStatusNotifier
from .services import ConfdCache, EndpointsService, NotifyingStatusCache


class Plugin:
    def load(self, dependencies: PluginDependencies) -> None:
        api = dependencies['api']
        ari = dependencies['ari']
        config = dependencies['config']
        status_aggregator = dependencies['status_aggregator']
        token_changed_subscribe = dependencies['token_changed_subscribe']
        bus_consumer = dependencies['bus_consumer']
        bus_publisher = dependencies['bus_publisher']

        confd_client = ConfdClient(**config['confd'])
        token_changed_subscribe(confd_client.set_token)

        # loaded in the background from the first token on, never by an event
        confd_cache = ConfdCache(confd_client)
        token_changed_subscribe(confd_cache.start)
        self._confd_cache = confd_cache
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
        confd_cache.on_ready(event_handler.replay_registry)
        confd_cache.on_ready(notifier.replay)

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

    def _set_async_tasks_completed(self) -> None:
        self._async_tasks_completed = True

    def _provide_status(self, status: StatusDict) -> None:
        ready = self._async_tasks_completed and self._confd_cache.ready
        status['plugins']['endpoints']['status'] = Status.ok if ready else Status.fail
        status['plugins']['endpoints']['confd_cache'] = self._confd_cache.status()
