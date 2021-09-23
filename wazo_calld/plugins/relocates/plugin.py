# Copyright 2017-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_confd_client import Client as ConfdClient
from wazo_amid_client import Client as AmidClient
from xivo.pubsub import CallbackCollector

from .notifier import RelocatesNotifier
from .http import (
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
        confd_client = ConfdClient(**config['confd'])

        token_changed_subscribe(amid_client.set_token)
        token_changed_subscribe(confd_client.set_token)

        relocates = RelocateCollection()
        state_factory = StateFactory(state_index, amid_client, ari.client)

        notifier = RelocatesNotifier(bus_publisher)
        relocates_service = RelocatesService(amid_client, ari.client, confd_client, notifier, relocates, state_factory)

        relocates_stasis = RelocatesStasis(ari, relocates)

        startup_callback_collector = CallbackCollector()
        ari.client_initialized_subscribe(startup_callback_collector.new_source())
        startup_callback_collector.subscribe(relocates_stasis.initialize)

        kwargs = {'resource_class_args': [relocates_service]}
        api.add_resource(UserRelocatesResource, '/users/me/relocates', **kwargs)
        api.add_resource(UserRelocateResource, '/users/me/relocates/<relocate_uuid>', **kwargs)
        api.add_resource(UserRelocateCompleteResource, '/users/me/relocates/<relocate_uuid>/complete', **kwargs)
        api.add_resource(UserRelocateCancelResource, '/users/me/relocates/<relocate_uuid>/cancel', **kwargs)
