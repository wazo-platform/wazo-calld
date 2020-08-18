# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_auth_client import Client as AuthClient
from wazo_amid_client import Client as AmidClient
from xivo.pubsub import CallbackCollector

from .http import (
    UserAdhocConferencesResource,
)
from .notifier import AdhocConferencesNotifier
from .services import AdhocConferencesService
from .stasis import AdhocConferencesStasis


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        amid_client = AmidClient(**config['amid'])
        auth_client = AuthClient(**config['auth'])

        token_changed_subscribe(amid_client.set_token)

        notifier = AdhocConferencesNotifier(bus_publisher)
        adhoc_conferences_service = AdhocConferencesService(amid_client, ari.client, notifier)

        startup_callback_collector = CallbackCollector()
        adhoc_conferences_stasis = AdhocConferencesStasis(ari, notifier)
        ari.client_initialized_subscribe(startup_callback_collector.new_source())
        startup_callback_collector.subscribe(adhoc_conferences_stasis.initialize)

        api.add_resource(UserAdhocConferencesResource, '/users/me/conferences/adhoc', resource_class_args=[adhoc_conferences_service, auth_client])
