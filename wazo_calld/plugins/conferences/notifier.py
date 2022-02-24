# Copyright 2019-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_bus.resources.conference.event import (
    ParticipantJoinedConferenceEvent,
    ParticipantLeftConferenceEvent,
    ParticipantMutedConferenceEvent,
    ParticipantTalkStartedConferenceEvent,
    ParticipantTalkStoppedConferenceEvent,
    ParticipantUnmutedConferenceEvent,
    RecordStartedConferenceEvent,
    RecordStoppedConferenceEvent,
    UserParticipantJoinedConferenceEvent,
    UserParticipantLeftConferenceEvent,
    UserParticipantTalkStartedConferenceEvent,
    UserParticipantTalkStoppedConferenceEvent,
)


class Participants:
    def __init__(self, *participants):
        self._participants = participants

    def valid_user_uuids(self):
        seen = set()
        for participant in self._participants:
            participant_user_uuid = participant['user_uuid']
            if participant_user_uuid and participant_user_uuid not in seen:
                seen.add(participant_user_uuid)
                yield participant_user_uuid


class ConferencesNotifier:

    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    @staticmethod
    def _build_headers(user_uuids=None, **kwargs):
        headers = {}
        for uuid in user_uuids or []:
            headers[f'user_uuid:{uuid}'] = True

        for kw in kwargs:
            if kw:
                headers[kw] = kwargs[kw]
        return headers if headers else None

    def participant_joined(self, tenant_uuid, conference_id, participant, participants_already_present):
        participants_uuids = list(Participants(participant, *participants_already_present).valid_user_uuids())

        for user_uuid_concerned in participants_uuids:
            user_event = UserParticipantJoinedConferenceEvent(conference_id, participant, user_uuid_concerned)
            headers = self._build_headers(
                user_uuids=[user_uuid_concerned],
                conference_id=conference_id,
                tenant_uuid=tenant_uuid,
            )
            self._bus_producer.publish(user_event, headers=headers)

        headers = self._build_headers(
            conference_id=conference_id,
            tenant_uuid=tenant_uuid,
            user_uuids=participants_uuids,
        )
        conference_event = ParticipantJoinedConferenceEvent(conference_id, participant)
        self._bus_producer.publish(conference_event, headers=headers)

    def participant_left(self, tenant_uuid, conference_id, participant, participants_already_present):
        participants_uuids = list(Participants(participant, *participants_already_present).valid_user_uuids())

        for user_uuid_concerned in participants_uuids:
            user_event = UserParticipantLeftConferenceEvent(conference_id, participant, user_uuid_concerned)
            headers = self._build_headers(
                user_uuids=[user_uuid_concerned],
                conference_id=conference_id,
                tenant_uuid=tenant_uuid,
            )
            self._bus_producer.publish(user_event, headers=headers)

        headers = self._build_headers(
            conference_id=conference_id,
            tenant_uuid=tenant_uuid,
            user_uuids=participants_uuids,
        )
        conference_event = ParticipantLeftConferenceEvent(conference_id, participant)
        self._bus_producer.publish(conference_event, headers=headers)

    def participant_muted(self, conference_id, tenant_uuid, participant):
        event = ParticipantMutedConferenceEvent(conference_id, participant)
        headers = self._build_headers(
            conference_id=conference_id,
            tenant_uuid=tenant_uuid,
        )
        self._bus_producer.publish(event, headers=headers)

    def participant_unmuted(self, conference_id, tenant_uuid, participant):
        event = ParticipantUnmutedConferenceEvent(conference_id, participant)
        headers = self._build_headers(
            conference_id=conference_id,
            tenant_uuid=tenant_uuid,
        )
        self._bus_producer.publish(event, headers=headers)

    def conference_record_started(self, conference_id, tenant_uuid):
        event = RecordStartedConferenceEvent(conference_id)
        headers = self._build_headers(
            conference_id=conference_id,
            tenant_uuid=tenant_uuid,
        )
        self._bus_producer.publish(event, headers=headers)

    def conference_record_stopped(self, conference_id, tenant_uuid):
        event = RecordStoppedConferenceEvent(conference_id)
        headers = self._build_headers(
            conference_id=conference_id,
            tenant_uuid=tenant_uuid,
        )
        self._bus_producer.publish(event, headers=headers)

    def participant_talk_started(self, conference_id, tenant_uuid, participant, participants):
        participants_uuids = list(Participants(*participants).valid_user_uuids())

        for user_uuid_concerned in participants_uuids:
            user_event = UserParticipantTalkStartedConferenceEvent(conference_id, participant, user_uuid_concerned)
            headers = self._build_headers(
                conference_id=conference_id,
                user_uuids=[user_uuid_concerned],
                tenant_uuid=tenant_uuid,
            )
            self._bus_producer.publish(user_event, headers=headers)

        event = ParticipantTalkStartedConferenceEvent(conference_id, participant)
        headers = self._build_headers(
            conference_id=conference_id,
            tenant_uuid=tenant_uuid,
            user_uuids=participants_uuids,
        )
        self._bus_producer.publish(event, headers=headers)

    def participant_talk_stopped(self, conference_id, tenant_uuid, participant, participants):
        participants_uuids = list(Participants(*participants).valid_user_uuids())

        for user_uuid_concerned in participants_uuids:
            user_event = UserParticipantTalkStoppedConferenceEvent(conference_id, participant, user_uuid_concerned)
            headers = self._build_headers(
                conference_id=conference_id,
                user_uuids=[user_uuid_concerned],
                tenant_uuid=tenant_uuid,
            )
            self._bus_producer.publish(user_event, headers=headers)

        event = ParticipantTalkStoppedConferenceEvent(conference_id, participant)
        headers = self._build_headers(
            conference_id=conference_id,
            tenant_uuid=tenant_uuid,
            user_uuids=participants_uuids,
        )
        self._bus_producer.publish(event, headers=headers)
