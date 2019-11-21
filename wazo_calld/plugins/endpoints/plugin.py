# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_confd_client import Client as ConfdClient

from .resources import TrunkEndpoints
from .services import EndpointsService


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        confd_client = ConfdClient(**config['confd'])
        token_changed_subscribe(confd_client.set_token)

        endpoints_service = EndpointsService(confd_client, ari.client)

        api.add_resource(
            TrunkEndpoints,
            '/endpoints/trunks',
            resource_class_args=[
                endpoints_service,
            ],
        )
