# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_amid_client import Client as AmidClient

from .resources import FaxesResource
from .services import FaxService


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        amid_client = AmidClient(**config['amid'])

        token_changed_subscribe(amid_client.set_token)

        fax_service = FaxService(amid_client, ari.client)

        api.add_resource(FaxesResource, '/fax', resource_class_args=[fax_service])
