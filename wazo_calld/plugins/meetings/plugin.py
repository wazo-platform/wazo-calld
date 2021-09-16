# Copyright 2018-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_auth_client import Client as AuthClient
from wazo_confd_client import Client as ConfdClient
from wazo_amid_client import Client as AmidClient

from .http import (
    MeetingParticipantsResource,
    MeetingParticipantsUserResource,
)
from .bus_consume import MeetingsBusEventHandler
from .notifier import MeetingsNotifier
from .services import MeetingsService


class Plugin:
    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        bus_consumer = dependencies['bus_consumer']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        amid_client = AmidClient(**config['amid'])
        auth_client = AuthClient(**config['auth'])
        confd_client = ConfdClient(**config['confd'])

        token_changed_subscribe(amid_client.set_token)
        token_changed_subscribe(confd_client.set_token)

        meetings_service = MeetingsService(amid_client, ari.client, confd_client)
        notifier = MeetingsNotifier(bus_publisher)
        bus_event_handler = MeetingsBusEventHandler(
            confd_client, notifier, meetings_service
        )
        bus_event_handler.subscribe(bus_consumer)

        api.add_resource(
            MeetingParticipantsResource,
            '/meetings/<meeting_uuid>/participants',
            resource_class_args=[meetings_service],
        )
        api.add_resource(
            MeetingParticipantsUserResource,
            '/users/me/meetings/<meeting_uuid>/participants',
            resource_class_args=[auth_client, meetings_service],
        )
