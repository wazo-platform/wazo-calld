# Copyright 2020-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_bus.resources.adhoc_conference.event import (
    AdhocConferenceCreatedUserEvent,
    AdhocConferenceDeletedUserEvent,
    AdhocConferenceParticipantJoinedUserEvent,
    AdhocConferenceParticipantLeftUserEvent,
)
from wazo_calld.plugins.calls.schemas import call_schema


class AdhocConferencesNotifier:
    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    def _build_headers(self, tenant_uuid, user_uuid):
        return {
            f'user_uuid:{user_uuid}': True,
            'tenant_uuid': tenant_uuid,
        }

    def created(self, adhoc_conference_id, tenant_uuid, host_user_uuid):
        event = AdhocConferenceCreatedUserEvent(adhoc_conference_id, host_user_uuid)
        headers = self._build_headers(tenant_uuid, host_user_uuid)
        self._bus_producer.publish(event, headers=headers)

    def deleted(self, adhoc_conference_id, tenant_uuid, host_user_uuid):
        event = AdhocConferenceDeletedUserEvent(adhoc_conference_id, host_user_uuid)
        headers = self._build_headers(tenant_uuid, host_user_uuid)
        self._bus_producer.publish(event, headers=headers)

    def participant_joined(
        self,
        adhoc_conference_id,
        other_participant_user_uuids,
        participant_call,
    ):
        for other_participant_user_uuid in other_participant_user_uuids:
            event = AdhocConferenceParticipantJoinedUserEvent(
                adhoc_conference_id,
                other_participant_user_uuid,
                call_schema.dump(participant_call),
            )
            headers = self._build_headers(
                participant_call.tenant_uuid,
                other_participant_user_uuid,
            )
            self._bus_producer.publish(event, headers=headers)

    def participant_left(
        self,
        adhoc_conference_id,
        other_participant_user_uuids,
        participant_call,
    ):
        for other_participant_user_uuid in other_participant_user_uuids:
            event = AdhocConferenceParticipantLeftUserEvent(
                adhoc_conference_id,
                other_participant_user_uuid,
                call_schema.dump(participant_call),
            )
            headers = self._build_headers(
                participant_call.tenant_uuid,
                other_participant_user_uuid,
            )
            self._bus_producer.publish(event, headers=headers)
