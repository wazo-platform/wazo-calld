# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_auth_client import Client as AuthClient
from wazo_confd_client import Client as ConfdClient
from xivo_amid_client import Client as AmidClient

from .resources import (
    ConferenceRecordResource,
    ParticipantMuteResource,
    ParticipantResource,
    ParticipantUnmuteResource,
    ParticipantsResource,
    ParticipantsUserResource,
)
from .bus_consume import ConferencesBusEventHandler
from .notifier import ConferencesNotifier
from .services import ConferencesService


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

        conferences_service = ConferencesService(amid_client, ari.client, confd_client)
        notifier = ConferencesNotifier(bus_publisher)
        bus_event_handler = ConferencesBusEventHandler(confd_client, notifier, conferences_service)
        bus_event_handler.subscribe(bus_consumer)

        api.add_resource(ParticipantsResource, '/conferences/<int:conference_id>/participants', resource_class_args=[conferences_service])
        api.add_resource(ParticipantsUserResource, '/users/me/conferences/<int:conference_id>/participants', resource_class_args=[auth_client, conferences_service])
        api.add_resource(ParticipantResource, '/conferences/<int:conference_id>/participants/<participant_id>', resource_class_args=[conferences_service])
        api.add_resource(ParticipantMuteResource, '/conferences/<int:conference_id>/participants/<participant_id>/mute', resource_class_args=[conferences_service])
        api.add_resource(ParticipantUnmuteResource, '/conferences/<int:conference_id>/participants/<participant_id>/unmute', resource_class_args=[conferences_service])
        api.add_resource(ConferenceRecordResource, '/conferences/<int:conference_id>/record', resource_class_args=[conferences_service])
