# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_amid_client import Client as AmidClient
from xivo_auth_client import Client as AuthClient
from xivo_confd_client import Client as ConfdClient

from .resources import (
    UserRelocatesResource,
    UserRelocateResource,
)
from .services import RelocatesService
from .stasis import RelocatesStasis
from .state import StateFactory, state_index
from .relocate import RelocateCollection


class Plugin(object):

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

        relocates = RelocateCollection()
        state_factory = StateFactory(state_index, amid_client, ari.client)

        relocates_service = RelocatesService(amid_client, ari.client, confd_client, relocates, state_factory)

        relocates_stasis = RelocatesStasis(ari.client, relocates)
        relocates_stasis.subscribe()

        api.add_resource(UserRelocatesResource, '/users/me/relocates', resource_class_args=[auth_client, relocates_service])
        api.add_resource(UserRelocateResource, '/users/me/relocates/<relocate_uuid>', resource_class_args=[auth_client, relocates_service])
