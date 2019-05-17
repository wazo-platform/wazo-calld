# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_auth_client import Client as AuthClient
from xivo_confd_client import Client as ConfdClient

from wazo_calld.ari_ import DEFAULT_APPLICATION_NAME

from .notifier import SwitchboardsNotifier
from .resources import (
    SwitchboardCallHeldAnswerResource,
    SwitchboardCallHeldResource,
    SwitchboardCallQueuedAnswerResource,
    SwitchboardCallsHeldResource,
    SwitchboardCallsQueuedResource,
)
from .services import SwitchboardsService
from .stasis import SwitchboardsStasis


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        auth_client = AuthClient(**config['auth'])
        confd_client = ConfdClient(**config['confd'])

        token_changed_subscribe(auth_client.set_token)
        token_changed_subscribe(confd_client.set_token)

        switchboards_notifier = SwitchboardsNotifier(bus_publisher)
        switchboards_service = SwitchboardsService(ari.client, confd_client, switchboards_notifier)

        ari.register_application(DEFAULT_APPLICATION_NAME)
        switchboards_stasis = SwitchboardsStasis(ari.client, confd_client, switchboards_notifier, switchboards_service)
        switchboards_stasis.subscribe()

        api.add_resource(
            SwitchboardCallsQueuedResource,
            '/switchboards/<switchboard_uuid>/calls/queued',
            resource_class_args=[switchboards_service],
        )
        api.add_resource(
            SwitchboardCallQueuedAnswerResource,
            '/switchboards/<switchboard_uuid>/calls/queued/<call_id>/answer',
            resource_class_args=[auth_client, switchboards_service],
        )
        api.add_resource(
            SwitchboardCallsHeldResource,
            '/switchboards/<switchboard_uuid>/calls/held',
            resource_class_args=[switchboards_service],
        )
        api.add_resource(
            SwitchboardCallHeldResource,
            '/switchboards/<switchboard_uuid>/calls/held/<call_id>',
            resource_class_args=[switchboards_service],
        )
        api.add_resource(
            SwitchboardCallHeldAnswerResource,
            '/switchboards/<switchboard_uuid>/calls/held/<call_id>/answer',
            resource_class_args=[auth_client, switchboards_service],
        )
