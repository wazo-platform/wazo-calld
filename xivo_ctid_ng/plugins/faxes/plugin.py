# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_amid_client import Client as AmidClient
from xivo_auth_client import Client as AuthClient
from xivo_confd_client import Client as ConfdClient

from .resources import (
    FaxesResource,
    UserFaxesResource,
)
from .services import FaxesService


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        amid_client = AmidClient(**config['amid'])
        auth_client = AuthClient(**config['auth'])
        confd_client = ConfdClient(**config['confd'])

        token_changed_subscribe(amid_client.set_token)
        token_changed_subscribe(confd_client.set_token)

        fax_service = FaxesService(amid_client, ari.client, confd_client)

        api.add_resource(FaxesResource, '/faxes', resource_class_args=[fax_service])
        api.add_resource(UserFaxesResource, '/users/me/faxes', resource_class_args=[auth_client, fax_service])
