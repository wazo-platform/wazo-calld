# -*- coding: UTF-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_amid_client import Client as AmidClient
from xivo_auth_client import Client as AuthClient
from xivo_confd_client import Client as ConfdClient

from .bus_consume import CallsBusEventHandler
from .resources import CallResource
from .resources import CallsResource
from .resources import ConnectCallToUserResource
from .resources import MyCallsResource
from .services import CallsService
from .stasis import CallsStasis


class Plugin(object):

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

        calls_service = CallsService(config['ari']['connection'], ari.client, confd_client)

        calls_stasis = CallsStasis(ari.client, collectd, bus_publisher, calls_service, config['uuid'], amid_client)
        calls_stasis.subscribe()

        calls_bus_event_handler = CallsBusEventHandler(ari.client, collectd, bus_publisher, calls_service, config['uuid'])
        calls_bus_event_handler.subscribe(bus_consumer)

        api.add_resource(CallsResource, '/calls', resource_class_args=[calls_service])
        api.add_resource(MyCallsResource, '/users/me/calls', resource_class_args=[auth_client, calls_service])
        api.add_resource(CallResource, '/calls/<call_id>', resource_class_args=[calls_service])
        api.add_resource(ConnectCallToUserResource, '/calls/<call_id>/user/<user_uuid>', resource_class_args=[calls_service])
