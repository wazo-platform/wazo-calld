# Copyright 2019-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_bus.resources.conference.event import (
    ConferenceParticipantJoinedEvent,
    ConferenceParticipantLeftEvent,
    ConferenceParticipantMutedEvent,
    ConferenceParticipantTalkStartedEvent,
    ConferenceParticipantTalkStoppedEvent,
    ConferenceParticipantUnmutedEvent,
    ConferenceRecordStartedEvent,
    ConferenceRecordStoppedEvent,
    ConferenceUserParticipantJoinedEvent,
    ConferenceUserParticipantLeftEvent,
    ConferenceUserParticipantTalkStartedEvent,
    ConferenceUserParticipantTalkStoppedEvent,
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

    def participant_joined(self, tenant_uuid, conference_id, participant, participants_already_present):
        participants_uuids = list(Participants(participant, *participants_already_present).valid_user_uuids())

        for user_uuid_concerned in participants_uuids:
            event = ConferenceUserParticipantJoinedEvent(
                conference_id, participant, tenant_uuid, user_uuid_concerned
            )
            self._bus_producer.publish(event)

        event = ConferenceParticipantJoinedEvent(
            conference_id, participant, tenant_uuid, participants_uuids
        )
        self._bus_producer.publish(event)

    def participant_left(self, tenant_uuid, conference_id, participant, participants_already_present):
        participants_uuids = list(Participants(participant, *participants_already_present).valid_user_uuids())

        for user_uuid_concerned in participants_uuids:
            event = ConferenceUserParticipantLeftEvent(conference_id, participant, tenant_uuid, user_uuid_concerned)
            self._bus_producer.publish(event)

        event = ConferenceParticipantLeftEvent(
            conference_id, participant, tenant_uuid, participants_uuids
        )
        self._bus_producer.publish(event)

    def participant_muted(self, conference_id, tenant_uuid, participant):
        event = ConferenceParticipantMutedEvent(conference_id, participant, tenant_uuid)
        self._bus_producer.publish(event)

    def participant_unmuted(self, conference_id, tenant_uuid, participant):
        event = ConferenceParticipantUnmutedEvent(conference_id, participant, tenant_uuid)
        self._bus_producer.publish(event)

    def conference_record_started(self, conference_id, tenant_uuid):
        event = ConferenceRecordStartedEvent(conference_id, tenant_uuid)
        self._bus_producer.publish(event)

    def conference_record_stopped(self, conference_id, tenant_uuid):
        event = ConferenceRecordStoppedEvent(conference_id, tenant_uuid)
        self._bus_producer.publish(event)

    def participant_talk_started(self, conference_id, tenant_uuid, participant, participants):
        participants_uuids = list(Participants(*participants).valid_user_uuids())

        for user_uuid_concerned in participants_uuids:
            event = ConferenceUserParticipantTalkStartedEvent(
                conference_id, participant, tenant_uuid, user_uuid_concerned
            )
            self._bus_producer.publish(event)

        event = ConferenceParticipantTalkStartedEvent(
            conference_id, participant, tenant_uuid, participants_uuids
        )
        self._bus_producer.publish(event)

    def participant_talk_stopped(self, conference_id, tenant_uuid, participant, participants):
        participants_uuids = list(Participants(*participants).valid_user_uuids())

        for user_uuid_concerned in participants_uuids:
            event = ConferenceUserParticipantTalkStoppedEvent(
                conference_id, participant, tenant_uuid, user_uuid_concerned
            )
            self._bus_producer.publish(event)

        event = ConferenceParticipantTalkStoppedEvent(
            conference_id, participant, tenant_uuid, participants_uuids
        )
        self._bus_producer.publish(event)
