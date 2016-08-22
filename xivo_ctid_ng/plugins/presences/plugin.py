# -*- coding: UTF-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_auth_client import Client as AuthClient
from xivo_ctid_client import Client as CtidClient

from .resources import LinePresencesResource, UserPresencesResource, UserMePresencesResource
from .services import LinePresencesService, UserPresencesService


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']

        auth_client = AuthClient(**config['auth'])
        ctid_client = CtidClient(**config['ctid'])

        user_presences_service = UserPresencesService(bus_publisher, ctid_client, config['ctid'])
        line_presences_service = LinePresencesService(ctid_client, config['ctid'])

        api.add_resource(UserPresencesResource, '/users/<user_uuid>/presences', resource_class_args=[user_presences_service])
        api.add_resource(UserMePresencesResource, '/users/me/presences', resource_class_args=[auth_client, user_presences_service])
        api.add_resource(LinePresencesResource, '/lines/<line_id>/presences', resource_class_args=[line_presences_service])
