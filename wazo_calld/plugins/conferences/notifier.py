# Copyright 2019-2020 The Wazo Authors  (see the AUTHORS file)
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

    def participant_joined(self, tenant_uuid, conference_id, participant, participants_already_present):
        participants = Participants(participant, *participants_already_present)
        for user_uuid_concerned in participants.valid_user_uuids():
            user_event = UserParticipantJoinedConferenceEvent(conference_id, participant, user_uuid_concerned)
            self._bus_producer.publish(user_event)

        headers = {
            'name': 'conference_participant_joined',
            'tenant_uuid': tenant_uuid,
            'conference_id': conference_id,
            'acl': 'event.conference_participants_joined',
        }
        for user_uuid_concerned in participants.valid_user_uuids():
            headers['user_uuid:{}'.format(user_uuid_concerned)] = True
        conference_event = ParticipantJoinedConferenceEvent(conference_id, participant)
        self._bus_producer.publish(conference_event, headers=headers)

    def participant_left(self, tenant_uuid, conference_id, participant, participants_already_present):
        participants = Participants(participant, *participants_already_present)
        for user_uuid_concerned in participants.valid_user_uuids():
            user_event = UserParticipantLeftConferenceEvent(conference_id, participant, user_uuid_concerned)
            self._bus_producer.publish(user_event)

        headers = {
            'name': 'conference_participant_left',
            'tenant_uuid': tenant_uuid,
            'conference_id': conference_id,
            'acl': 'event.conference_participants_left',
        }
        for user_uuid_concerned in participants.valid_user_uuids():
            headers['user_uuid:{}'.format(user_uuid_concerned)] = True
        conference_event = ParticipantLeftConferenceEvent(conference_id, participant)
        self._bus_producer.publish(conference_event, headers=headers)

    def participant_muted(self, conference_id, participant):
        event = ParticipantMutedConferenceEvent(conference_id, participant)
        self._bus_producer.publish(event)

    def participant_unmuted(self, conference_id, participant):
        event = ParticipantUnmutedConferenceEvent(conference_id, participant)
        self._bus_producer.publish(event)

    def conference_record_started(self, conference_id):
        event = RecordStartedConferenceEvent(conference_id)
        self._bus_producer.publish(event)

    def conference_record_stopped(self, conference_id):
        event = RecordStoppedConferenceEvent(conference_id)
        self._bus_producer.publish(event)

    def participant_talk_started(self, conference_id, participant, participants):
        for user_uuid_concerned in Participants(*participants).valid_user_uuids():
            user_event = UserParticipantTalkStartedConferenceEvent(conference_id, participant, user_uuid_concerned)
            self._bus_producer.publish(user_event)

        event = ParticipantTalkStartedConferenceEvent(conference_id, participant)
        self._bus_producer.publish(event)

    def participant_talk_stopped(self, conference_id, participant, participants):
        for user_uuid_concerned in Participants(*participants).valid_user_uuids():
            user_event = UserParticipantTalkStoppedConferenceEvent(conference_id, participant, user_uuid_concerned)
            self._bus_producer.publish(user_event)

        event = ParticipantTalkStoppedConferenceEvent(conference_id, participant)
        self._bus_producer.publish(event)
