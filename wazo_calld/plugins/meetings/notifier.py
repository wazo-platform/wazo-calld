# Copyright 2019-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_bus.resources.meeting.event import (
    ParticipantJoinedMeetingEvent,
    ParticipantLeftMeetingEvent,
    UserParticipantJoinedMeetingEvent,
    UserParticipantLeftMeetingEvent,
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


class MeetingsNotifier:
    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    def participant_joined(
        self, tenant_uuid, meeting_uuid, participant, participants_already_present
    ):
        participants = Participants(participant, *participants_already_present)
        for user_uuid_concerned in participants.valid_user_uuids():
            user_event = UserParticipantJoinedMeetingEvent(
                meeting_uuid, participant, user_uuid_concerned
            )
            self._bus_producer.publish(user_event)

        headers = {
            'name': 'meeting_participant_joined',
            'tenant_uuid': tenant_uuid,
            'meeting_uuid': meeting_uuid,
        }
        for user_uuid_concerned in participants.valid_user_uuids():
            headers['user_uuid:{}'.format(user_uuid_concerned)] = True
        meeting_event = ParticipantJoinedMeetingEvent(meeting_uuid, participant)
        self._bus_producer.publish(meeting_event, headers=headers)

    def participant_left(
        self, tenant_uuid, meeting_uuid, participant, participants_already_present
    ):
        participants = Participants(participant, *participants_already_present)
        for user_uuid_concerned in participants.valid_user_uuids():
            user_event = UserParticipantLeftMeetingEvent(
                meeting_uuid, participant, user_uuid_concerned
            )
            self._bus_producer.publish(user_event)

        headers = {
            'name': 'meeting_participant_left',
            'tenant_uuid': tenant_uuid,
            'meeting_uuid': meeting_uuid,
        }
        for user_uuid_concerned in participants.valid_user_uuids():
            headers['user_uuid:{}'.format(user_uuid_concerned)] = True
        meeting_event = ParticipantLeftMeetingEvent(meeting_uuid, participant)
        self._bus_producer.publish(meeting_event, headers=headers)
