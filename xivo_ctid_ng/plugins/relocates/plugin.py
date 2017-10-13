# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_auth_client import Client as AuthClient
from xivo_confd_client import Client as ConfdClient

from .resources import UserRelocatesResource
from .services import RelocatesService
from .stasis import RelocatesStasis
from .state import state_factory
from .relocate_lock import RelocateLock
from .relocate import RelocateCollection


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        auth_client = AuthClient(**config['auth'])
        confd_client = ConfdClient(**config['confd'])

        token_changed_subscribe(confd_client.set_token)

        relocates = RelocateCollection()
        relocate_lock = RelocateLock()

        relocates_service = RelocatesService(ari.client, confd_client, relocates, state_factory,  relocate_lock)

        relocates_stasis = RelocatesStasis(ari.client, relocates, state_factory)
        relocates_stasis.subscribe()

        state_factory.set_dependencies(ari.client, relocates_service, relocate_lock)

        api.add_resource(UserRelocatesResource, '/users/me/relocates', resource_class_args=[auth_client, relocates_service])
