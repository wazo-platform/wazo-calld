# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import time

from requests import RequestException

from xivo_amid_client import Client as AmidClient
from xivo_auth_client import Client as AuthClient
from xivo_confd_client import Client as ConfdClient

from .notifier import ApplicationNotifier
from .resources import (
    ApplicationItem,
)
from .services import ApplicationService
from .stasis import ApplicationStasis, AppNameHelper


class RegisterStasisApps(object):

    _connection_retry = 10
    _retry_delay = 0.2

    def __init__(self, ari, confd):
        self.ari = ari
        self.confd = confd
        self._initialized = False

    def trigger_registers(self, token):
        if self._initialized:
            return

        for n in xrange(self._connection_retry):
            try:
                applications = self.confd.applications.list()['items']
                break
            except RequestException:
                if n < self._connection_retry - 1:
                    time.sleep(self._retry_delay)
                else:
                    raise

        for application in applications:
            app = AppNameHelper.to_name(application['uuid'])
            self.ari.register_application(app)
        self.ari.reload()
        self._initialized = True


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

        register_stasis_app = RegisterStasisApps(ari, confd_client)
        token_changed_subscribe(register_stasis_app.trigger_registers)

        stasis = ApplicationStasis(ari.client, confd_client, service, notifier)
        token_changed_subscribe(stasis.initialize_destination)

        api.add_resource(
            ApplicationItem,
            '/applications/<uuid:application_uuid>',
            resource_class_args=[service],
        )
