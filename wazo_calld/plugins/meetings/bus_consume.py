# Copyright 2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from wazo_calld.plugin_helpers.confd import Meeting
from wazo_calld.plugin_helpers.exceptions import NoSuchMeeting

from .meeting import (
    AsteriskMeeting,
    InvalidMeetingConfbridgeName,
)
from .schemas import participant_schema

logger = logging.getLogger(__name__)


class MeetingsBusEventHandler:
    def __init__(self, confd, notifier, service):
        self._confd = confd
        self._notifier = notifier
        self._service = service

    def subscribe(self, bus_consumer):
        bus_consumer.on_ami_event('ConfbridgeJoin', self._notify_participant_joined)
        bus_consumer.on_ami_event('ConfbridgeLeave', self._notify_participant_left)
        bus_consumer.on_event('meeting_deleted', self._on_meeting_deleted)

    def _notify_participant_joined(self, event):
        try:
            meeting_uuid = AsteriskMeeting.from_confbridge_name(event['Conference']).uuid
        except InvalidMeetingConfbridgeName:
            return

        try:
            meeting = Meeting.from_uuid(meeting_uuid, self._confd)
        except NoSuchMeeting:
            logger.debug(
                'Ignored participant joining meeting %s: no such meeting', meeting_uuid
            )
            return

        logger.debug('Participant joined meeting %s', meeting_uuid)
        raw_participant = {
            'id': event['Uniqueid'],
            'caller_id_name': event['CallerIDName'],
            'caller_id_number': event['CallerIDNum'],
            'muted': event['Muted'] == 'Yes',
            'answered_time': 0,
            'admin': event['Admin'] == 'Yes',
            'language': event['Language'],
            'call_id': event['Uniqueid'],
            'user_uuid': event.get('ChanVariable', {}).get('XIVO_USERUUID'),
        }

        participant = participant_schema.load(raw_participant)

        participants_already_present = self._service.list_participants(
            meeting.tenant_uuid, meeting_uuid
        )

        self._notifier.participant_joined(
            meeting.tenant_uuid, meeting_uuid, participant, participants_already_present
        )

    def _notify_participant_left(self, event):
        try:
            meeting_uuid = AsteriskMeeting.from_confbridge_name(event['Conference']).uuid
        except InvalidMeetingConfbridgeName:
            return

        try:
            meeting = Meeting.from_uuid(meeting_uuid, self._confd)
        except NoSuchMeeting:
            logger.debug(
                'Ignored participant joining meeting %s: no such meeting', meeting_uuid
            )
            return

        logger.debug('Participant left meeting %s', meeting_uuid)
        raw_participant = {
            'id': event['Uniqueid'],
            'caller_id_name': event['CallerIDName'],
            'caller_id_number': event['CallerIDNum'],
            'muted': False,
            'answered_time': '0',
            'admin': event['Admin'] == 'Yes',
            'language': event['Language'],
            'call_id': event['Uniqueid'],
            'user_uuid': event.get('ChanVariable', {}).get('XIVO_USERUUID'),
        }

        participant = participant_schema.load(raw_participant)

        participants_already_present = self._service.list_participants(
            meeting.tenant_uuid, meeting_uuid
        )

        self._notifier.participant_left(
            meeting.tenant_uuid, meeting_uuid, participant, participants_already_present
        )

    def _on_meeting_deleted(self, event):
        meeting_uuid = event['uuid']
        self._service.kick_all_participants(meeting_uuid)
