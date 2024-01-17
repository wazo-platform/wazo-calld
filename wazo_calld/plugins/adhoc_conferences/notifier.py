# Copyright 2020-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_bus.resources.adhoc_conference.event import (
    AdhocConferenceCreatedEvent,
    AdhocConferenceDeletedEvent,
    AdhocConferenceParticipantJoinedEvent,
    AdhocConferenceParticipantLeftEvent,
)


class AdhocConferencesNotifier:
    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    def _build_headers(self, tenant_uuid, user_uuid):
        return {
            f'user_uuid:{user_uuid}': True,
            'tenant_uuid': tenant_uuid,
        }

    def created(self, adhoc_conference_id, tenant_uuid, host_user_uuid):
        event = AdhocConferenceCreatedEvent(
            adhoc_conference_id, tenant_uuid, host_user_uuid
        )
        self._bus_producer.publish(event)

    def deleted(self, adhoc_conference_id, tenant_uuid, host_user_uuid):
        event = AdhocConferenceDeletedEvent(
            adhoc_conference_id, tenant_uuid, host_user_uuid
        )
        self._bus_producer.publish(event)

    def participant_joined(
        self,
        adhoc_conference_id,
        other_participant_user_uuids,
        participant_call,
    ):
        for other_participant_user_uuid in other_participant_user_uuids:
            event = AdhocConferenceParticipantJoinedEvent(
                adhoc_conference_id,
                participant_call.id_,
                participant_call.tenant_uuid,
                other_participant_user_uuid,
            )
            self._bus_producer.publish(event)

    def participant_left(
        self,
        adhoc_conference_id,
        other_participant_user_uuids,
        participant_call,
    ):
        for other_participant_user_uuid in other_participant_user_uuids:
            event = AdhocConferenceParticipantLeftEvent(
                adhoc_conference_id,
                participant_call.id_,
                participant_call.tenant_uuid,
                other_participant_user_uuid,
            )
            self._bus_producer.publish(event)
