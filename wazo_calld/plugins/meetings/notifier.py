# Copyright 2021-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_bus.resources.meeting.event import (
    MeetingParticipantJoinedEvent,
    MeetingParticipantLeftEvent,
    MeetingUserParticipantJoinedEvent,
    MeetingUserParticipantLeftEvent,
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
        participants_uuids = list(participants.valid_user_uuids())

        for user_uuid_concerned in participants_uuids:
            user_event = MeetingUserParticipantJoinedEvent(
                participant, meeting_uuid, tenant_uuid, user_uuid_concerned
            )
            self._bus_producer.publish(user_event)

        event = MeetingParticipantJoinedEvent(participant, meeting_uuid, tenant_uuid)
        self._bus_producer.publish(event)

    def participant_left(
        self, tenant_uuid, meeting_uuid, participant, participants_already_present
    ):
        participants = Participants(participant, *participants_already_present)
        participants_uuids = list(participants.valid_user_uuids())

        for user_uuid_concerned in participants_uuids:
            user_event = MeetingUserParticipantLeftEvent(
                participant, meeting_uuid, tenant_uuid, user_uuid_concerned
            )
            self._bus_producer.publish(user_event)

        event = MeetingParticipantLeftEvent(participant, meeting_uuid, tenant_uuid)
        self._bus_producer.publish(event)
