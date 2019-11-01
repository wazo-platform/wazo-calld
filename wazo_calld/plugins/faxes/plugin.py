# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_auth_client import Client as AuthClient
from wazo_confd_client import Client as ConfdClient
from wazo_amid_client import Client as AmidClient

from .bus_consume import FaxesBusEventHandler
from .notifier import FaxesNotifier
from .resources import (
    FaxesResource,
    UserFaxesResource,
)
from .services import FaxesService


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        bus_consumer = dependencies['bus_consumer']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        amid_client = AmidClient(**config['amid'])
        auth_client = AuthClient(**config['auth'])
        confd_client = ConfdClient(**config['confd'])

        token_changed_subscribe(amid_client.set_token)
        token_changed_subscribe(confd_client.set_token)

        notifier = FaxesNotifier(bus_publisher)
        fax_service = FaxesService(amid_client, ari.client, confd_client, notifier)
        bus_event_handler = FaxesBusEventHandler(notifier)
        bus_event_handler.subscribe(bus_consumer)

        api.add_resource(FaxesResource, '/faxes', resource_class_args=[fax_service])
        api.add_resource(UserFaxesResource, '/users/me/faxes', resource_class_args=[auth_client, fax_service])
