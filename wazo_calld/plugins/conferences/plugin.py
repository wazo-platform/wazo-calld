# Copyright 2018-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_confd_client import Client as ConfdClient
from wazo_amid_client import Client as AmidClient

from .http import (
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
        channel_proxy = dependencies['channel_proxy']

        amid_client = AmidClient(**config['amid'])
        confd_client = ConfdClient(**config['confd'])

        token_changed_subscribe(amid_client.set_token)
        token_changed_subscribe(confd_client.set_token)

        conferences_service = ConferencesService(
            amid_client,
            ari.client,
            channel_proxy,
            confd_client,
        )
        notifier = ConferencesNotifier(bus_publisher)
        bus_event_handler = ConferencesBusEventHandler(
            confd_client, notifier, conferences_service
        )
        bus_event_handler.subscribe(bus_consumer)

        kwargs = {'resource_class_args': [conferences_service]}
        api.add_resource(
            ParticipantsResource,
            '/conferences/<int:conference_id>/participants',
            **kwargs
        )
        api.add_resource(
            ParticipantsUserResource,
            '/users/me/conferences/<int:conference_id>/participants',
            **kwargs
        )
        api.add_resource(
            ParticipantResource,
            '/conferences/<int:conference_id>/participants/<participant_id>',
            **kwargs
        )
        api.add_resource(
            ParticipantMuteResource,
            '/conferences/<int:conference_id>/participants/<participant_id>/mute',
            **kwargs
        )
        api.add_resource(
            ParticipantUnmuteResource,
            '/conferences/<int:conference_id>/participants/<participant_id>/unmute',
            **kwargs
        )
        api.add_resource(
            ConferenceRecordResource,
            '/conferences/<int:conference_id>/record',
            **kwargs
        )
