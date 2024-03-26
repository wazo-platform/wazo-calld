# Copyright 2024 The Wazo Authors (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from wazo_amid_client import Client as AmidClient
from wazo_confd_client import Client as ConfdClient

from .bus_consume import ParkingLotEventsHandler
from .http import ParkCallResource, ParkingLotResource, UserCallParkResource
from .notifier import ParkingNotifier
from .services import ParkingService

if TYPE_CHECKING:
    from collections.abc import Mapping

    from flask_restful import Api
    from xivo.token_renewer import Callback

    from wazo_calld.ari_ import CoreARI as AriClient
    from wazo_calld.bus import CoreBusConsumer, CoreBusPublisher


class Plugin:
    def load(self, dependencies: Mapping) -> None:
        api: Api = dependencies['api']
        ari: AriClient = dependencies['ari']
        bus_consumer: CoreBusConsumer = dependencies['bus_consumer']
        bus_publisher: CoreBusPublisher = dependencies['bus_publisher']
        config: Mapping = dependencies['config']
        token_changed_subscribe: Callable[[Callback], None] = dependencies[
            'token_changed_subscribe'
        ]

        confd_client = ConfdClient(**config['confd'])
        amid_client = AmidClient(**config['amid'])

        token_changed_subscribe(confd_client.set_token)
        token_changed_subscribe(amid_client.set_token)

        notifier = ParkingNotifier(bus_publisher)
        service = ParkingService(amid_client, ari, bus_consumer, confd_client, notifier)
        ParkingLotEventsHandler(ari, bus_consumer, notifier, service)

        self.set_resources(api, service)

    def set_resources(self, api: Api, service: ParkingService) -> None:
        api.add_resource(
            ParkingLotResource,
            '/parkinglots/<int:parking_id>',
            resource_class_args=[service],
        )

        api.add_resource(
            ParkCallResource,
            '/calls/<call_id>/park',
            resource_class_args=[service],
        )

        api.add_resource(
            UserCallParkResource,
            '/users/me/calls/<call_id>/park',
            resource_class_args=[service],
        )
