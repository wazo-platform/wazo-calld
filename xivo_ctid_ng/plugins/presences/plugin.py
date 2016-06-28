# -*- coding: UTF-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_auth_client import Client as AuthClient
from xivo_ctid_client import Client as CtidClient

from .resources import PresencesResource, UserPresencesResource
from .services import PresencesService


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']

        auth_client = AuthClient(**config['auth'])
        ctid_client = CtidClient(**config['ctid']) 

        presences_service = PresencesService(bus_publisher, ctid_client, config['ctid'])

        api.add_resource(PresencesResource, '/users/<user_uuid>/presences', resource_class_args=[presences_service])
        api.add_resource(UserPresencesResource, '/users/me/presences', resource_class_args=[auth_client, presences_service])
