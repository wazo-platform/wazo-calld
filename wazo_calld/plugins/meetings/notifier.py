# Copyright 2021-2022 The Wazo Authors  (see the AUTHORS file)
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

    @staticmethod
    def _build_headers(user_uuids=None, **kwargs):
        headers = {}
        for key, value in kwargs.items():
            headers[key] = value

        for uuid in user_uuids or []:
            headers[f'user_uuid:{uuid}'] = True

        return headers

    def participant_joined(
        self, tenant_uuid, meeting_uuid, participant, participants_already_present
    ):
        participants = Participants(participant, *participants_already_present)
        participants_uuids = list(participants.valid_user_uuids())

        for user_uuid_concerned in participants_uuids:
            user_event = UserParticipantJoinedMeetingEvent(
                meeting_uuid, participant, user_uuid_concerned
            )
            headers = self._build_headers(
                meeting_uuid=meeting_uuid,
                tenant_uuid=tenant_uuid,
                user_uuids=[user_uuid_concerned],
            )
            self._bus_producer.publish(user_event, headers=headers)

        headers = self._build_headers(
            meeting_uuid=meeting_uuid,
            tenant_uuid=tenant_uuid,
            user_uuids=participants_uuids,
        )
        meeting_event = ParticipantJoinedMeetingEvent(meeting_uuid, participant)
        self._bus_producer.publish(meeting_event, headers=headers)

    def participant_left(
        self, tenant_uuid, meeting_uuid, participant, participants_already_present
    ):
        participants = Participants(participant, *participants_already_present)
        participants_uuids = list(participants.valid_user_uuids())

        for user_uuid_concerned in participants_uuids:
            user_event = UserParticipantLeftMeetingEvent(
                meeting_uuid, participant, user_uuid_concerned
            )
            headers = self._build_headers(
                meeting_uuid=meeting_uuid,
                tenant_uuid=tenant_uuid,
                user_uuids=[user_uuid_concerned],
            )
            self._bus_producer.publish(user_event, headers=headers)

        headers = self._build_headers(
            meeting_uuid=meeting_uuid,
            tenant_uuid=tenant_uuid,
            user_uuids=participants_uuids,
        )
        meeting_event = ParticipantLeftMeetingEvent(meeting_uuid, participant)
        self._bus_producer.publish(meeting_event, headers=headers)
