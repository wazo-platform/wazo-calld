# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from wazo_amid_client import Client as AmidClient
from wazo_confd_client import Client as ConfdClient
from xivo.pubsub import CallbackCollector
from xivo.status import Status

from wazo_calld.types import PluginDependencies, StatusDict

from .bus import EventHandler
from .http import LineEndpoints, TrunkEndpoints
from .identity import EndpointIdentities, IdentityMap
from .notifier import EndpointStatusNotifier
from .services import EndpointsService, NotifyingStatusCache


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

        amid_client = AmidClient(**config['amid'])
        token_changed_subscribe(amid_client.set_token)

        identity_map = IdentityMap()
        identities = EndpointIdentities(
            identity_map, ari.client, confd_client, amid_client
        )
        notifier = EndpointStatusNotifier(bus_publisher, identities)

        status_cache = NotifyingStatusCache(notifier.endpoint_updated, ari.client)
        endpoints_service = EndpointsService(confd_client, status_cache)

        self._async_tasks_completed = False
        startup_callback_collector = CallbackCollector()
        ari.client_initialized_subscribe(startup_callback_collector.new_source())
        startup_callback_collector.subscribe(status_cache.initialize)
        startup_callback_collector.subscribe(self._set_async_tasks_completed)

        event_handler = EventHandler(status_cache, identity_map, identities)
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

    def _set_async_tasks_completed(self) -> None:
        self._async_tasks_completed = True

    def _provide_status(self, status: StatusDict) -> None:
        value = Status.ok if self._async_tasks_completed else Status.fail
        status['plugins']['endpoints']['status'] = value
