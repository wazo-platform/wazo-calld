# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_auth_client import Client as AuthClient
from wazo_confd_client import Client as ConfdClient
from wazo_amid_client import Client as AmidClient

from wazo_calld.ari_ import DEFAULT_APPLICATION_NAME

from .bus_consume import CallsBusEventHandler
from .dial_echo import DialEchoManager
from .resources import (
    CallResource,
    CallsResource,
    ConnectCallToUserResource,
    MyCallResource,
    MyCallsResource,
)
from .services import CallsService
from .stasis import CallsStasis


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        bus_consumer = dependencies['bus_consumer']
        bus_publisher = dependencies['bus_publisher']
        collectd = dependencies['collectd']
        token_changed_subscribe = dependencies['token_changed_subscribe']
        config = dependencies['config']

        amid_client = AmidClient(**config['amid'])
        token_changed_subscribe(amid_client.set_token)

        auth_client = AuthClient(**config['auth'])
        confd_client = ConfdClient(**config['confd'])

        token_changed_subscribe(confd_client.set_token)

        dial_echo_manager = DialEchoManager()

        calls_service = CallsService(amid_client, config['ari']['connection'], ari.client, confd_client, dial_echo_manager)

        ari.register_application(DEFAULT_APPLICATION_NAME)
        calls_stasis = CallsStasis(ari.client, collectd, bus_publisher, calls_service, config['uuid'], amid_client)
        calls_stasis.subscribe()

        calls_bus_event_handler = CallsBusEventHandler(amid_client, ari.client, collectd, bus_publisher, calls_service, config['uuid'], dial_echo_manager)
        calls_bus_event_handler.subscribe(bus_consumer)

        api.add_resource(CallsResource, '/calls', resource_class_args=[calls_service])
        api.add_resource(MyCallsResource, '/users/me/calls', resource_class_args=[auth_client, calls_service])
        api.add_resource(CallResource, '/calls/<call_id>', resource_class_args=[calls_service])
        api.add_resource(MyCallResource, '/users/me/calls/<call_id>', resource_class_args=[auth_client, calls_service])
        api.add_resource(ConnectCallToUserResource, '/calls/<call_id>/user/<user_uuid>', resource_class_args=[calls_service])
