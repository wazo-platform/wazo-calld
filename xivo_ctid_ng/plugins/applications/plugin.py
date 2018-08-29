# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_amid_client import Client as AmidClient
from xivo_auth_client import Client as AuthClient
from xivo_confd_client import Client as ConfdClient

from .notifier import ApplicationNotifier
from .resources import (
    ApplicationItem,
)
from .services import ApplicationService
from .stasis import ApplicationStasis


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        config = dependencies['config']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        auth_client = AuthClient(**config['auth'])
        confd_client = ConfdClient(**config['confd'])
        amid_client = AmidClient(**config['amid'])

        token_changed_subscribe(amid_client.set_token)
        token_changed_subscribe(auth_client.set_token)
        token_changed_subscribe(confd_client.set_token)

        notifier = ApplicationNotifier(bus_publisher)
        service = ApplicationService(ari.client, confd_client, amid_client, notifier)

        stasis = ApplicationStasis(ari, confd_client, service, notifier)
        token_changed_subscribe(stasis.initialize)

        api.add_resource(
            ApplicationItem,
            '/applications/<uuid:application_uuid>',
            resource_class_args=[service],
        )
