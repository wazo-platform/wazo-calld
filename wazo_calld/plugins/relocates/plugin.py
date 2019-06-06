# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_auth_client import Client as AuthClient
from wazo_confd_client import Client as ConfdClient
from xivo_amid_client import Client as AmidClient

from wazo_calld.ari_ import DEFAULT_APPLICATION_NAME

from .notifier import RelocatesNotifier
from .resources import (
    UserRelocateCancelResource,
    UserRelocateCompleteResource,
    UserRelocateResource,
    UserRelocatesResource,
)
from .services import RelocatesService
from .stasis import RelocatesStasis
from .state import StateFactory, state_index
from .relocate import RelocateCollection


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        amid_client = AmidClient(**config['amid'])
        auth_client = AuthClient(**config['auth'])
        confd_client = ConfdClient(**config['confd'])

        token_changed_subscribe(amid_client.set_token)
        token_changed_subscribe(confd_client.set_token)

        relocates = RelocateCollection()
        state_factory = StateFactory(state_index, amid_client, ari.client)

        notifier = RelocatesNotifier(bus_publisher)
        relocates_service = RelocatesService(amid_client, ari.client, confd_client, notifier, relocates, state_factory)

        ari.register_application(DEFAULT_APPLICATION_NAME)
        relocates_stasis = RelocatesStasis(ari.client, relocates)
        relocates_stasis.subscribe()

        api.add_resource(UserRelocatesResource, '/users/me/relocates', resource_class_args=[auth_client, relocates_service])
        api.add_resource(UserRelocateResource, '/users/me/relocates/<relocate_uuid>', resource_class_args=[auth_client, relocates_service])
        api.add_resource(UserRelocateCompleteResource, '/users/me/relocates/<relocate_uuid>/complete', resource_class_args=[auth_client, relocates_service])
        api.add_resource(UserRelocateCancelResource, '/users/me/relocates/<relocate_uuid>/cancel', resource_class_args=[auth_client, relocates_service])
