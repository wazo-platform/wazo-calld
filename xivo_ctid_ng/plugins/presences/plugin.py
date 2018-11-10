# -*- coding: UTF-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_auth_client import Client as AuthClient
from xivo_ctid_client import Client as CtidClient

from .resources import LinePresencesResource, UserPresencesResource, UserMePresencesResource
from .services import CtidNgClientFactory, LinePresencesService, UserPresencesService
from .websocketd_client import Client as WebsocketdClient


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        auth_client = AuthClient(**config['auth'])
        ctid_client = CtidClient(**config['ctid'])
        websocketd_client = WebsocketdClient(**config['websocketd'])

        token_changed_subscribe(websocketd_client.set_token)
        local_xivo_uuid = config['uuid']

        ctid_ng_client_factory = CtidNgClientFactory(
            config['consul'], config['remote_credentials'])
        user_presences_service = UserPresencesService(
            bus_publisher, websocketd_client, local_xivo_uuid, ctid_ng_client_factory)
        line_presences_service = LinePresencesService(
            ctid_client, config['ctid'], local_xivo_uuid, ctid_ng_client_factory)

        api.add_resource(UserPresencesResource,
                         '/users/<user_uuid>/presences',
                         resource_class_args=[user_presences_service])
        api.add_resource(UserMePresencesResource,
                         '/users/me/presences',
                         resource_class_args=[auth_client, user_presences_service])
        api.add_resource(LinePresencesResource,
                         '/lines/<int:line_id>/presences',
                         resource_class_args=[line_presences_service])
