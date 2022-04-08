# Copyright 2021-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from marshmallow import ValidationError
from requests import RequestException
from wazo_amid_client.exceptions import AmidProtocolError
from wazo_calld.plugin_helpers.confd import Meeting
from wazo_calld.plugin_helpers.ari_ import Channel
from wazo_calld.plugin_helpers.exceptions import (
    WazoAmidError,
)

from .exceptions import (
    MeetingParticipantError,
    NoSuchMeeting,
    NoSuchMeetingParticipant,
    UserNotParticipant,
)
from .schemas import participant_schema

logger = logging.getLogger(__name__)


class MeetingsService:
    def __init__(self, amid, ari, confd, config):
        self._amid = amid
        self._ari = ari
        self._confd = confd
        self._max_participants = config['max_meeting_participants']

    def get_status(self, meeting_uuid):
        tenant_uuid = None
        meeting = Meeting(tenant_uuid, meeting_uuid, self._confd)

        if not meeting.exists():
            raise NoSuchMeeting(tenant_uuid, meeting_uuid)

        try:
            participant_list = self._amid.action(
                'ConfBridgeList',
                {'Conference': meeting.asterisk_name()},
            )
            participant_count = len(participant_list) - 2  # 1 event for the success and on for the list complete
        except AmidProtocolError as e:
            if e.message in [
                'No active conferences.',
                'No Conference by that name found.'
            ]:
                participant_count = 0
            else:
                raise MeetingParticipantError(
                    tenant_uuid,
                    meeting_uuid,
                    participant_id=None,
                    message=e.message,
                )
        except RequestException as e:
            raise WazoAmidError(self._amid, e)

        return {'full': participant_count >= self._max_participants}

    def list_participants(self, tenant_uuid, meeting_uuid):
        meeting = Meeting(tenant_uuid, meeting_uuid, self._confd)

        if not meeting.exists():
            raise NoSuchMeeting(tenant_uuid, meeting_uuid)

        try:
            participant_list = self._amid.action(
                'ConfBridgeList',
                {'Conference': meeting.asterisk_name()},
            )
        except AmidProtocolError as e:
            if e.message in [
                'No active conferences.',
                'No Conference by that name found.',
            ]:
                return []
            raise MeetingParticipantError(
                tenant_uuid,
                meeting_uuid,
                participant_id=None,
                message=e.message,
            )
        except RequestException as e:
            raise WazoAmidError(self._amid, e)

        result = []
        del participant_list[0]
        for participant_list_item in participant_list:
            if participant_list_item['Event'] != 'ConfbridgeList':
                continue

            raw_participant = {
                'id': participant_list_item['Uniqueid'],
                'caller_id_name': participant_list_item['CallerIDName'],
                'caller_id_number': participant_list_item['CallerIDNum'],
                'call_id': participant_list_item['Uniqueid'],
                'user_uuid': Channel(
                    participant_list_item['Uniqueid'], self._ari
                ).user(),
            }
            try:
                participant = participant_schema.load(raw_participant)
            except ValidationError as e:
                raise MeetingParticipantError(
                    tenant_uuid, meeting_uuid, participant_id=None, message=str(e)
                )
            result.append(participant)

        return result

    def user_list_participants(self, tenant_uuid, user_uuid, conference_id):
        participants = self.list_participants(tenant_uuid, conference_id)
        user_is_participant = any(
            participant['user_uuid'] == user_uuid for participant in participants
        )
        if not user_is_participant:
            raise UserNotParticipant(tenant_uuid, user_uuid, conference_id)
        return participants

    def kick_all_participants(self, meeting_uuid):
        meeting = Meeting(meeting_uuid=meeting_uuid)
        try:
            self._amid.action(
                'ConfbridgeKick',
                {
                    'Conference': meeting.asterisk_name(),
                    'Channel': 'all',
                },
            )
        except AmidProtocolError as e:
            if e.message in [
                'No Conference by that name found.',  # This conference is not running at this time.
                'No active conferences.',    # No conferences are taking place at this time.
            ]:
                logger.debug(
                    'No participants found to kick out of meeting %s', meeting_uuid
                )
                return
            raise

    def kick_participant(self, tenant_uuid, meeting_uuid, participant_id):
        meeting = Meeting(tenant_uuid, meeting_uuid, self._confd)
        if not meeting.exists():
            raise NoSuchMeeting(tenant_uuid, meeting_uuid)

        channel = Channel(participant_id, self._ari)
        try:
            self._amid.action(
                'ConfbridgeKick',
                {
                    'Conference': meeting.asterisk_name(),
                    'Channel': channel.asterisk_name(),
                },
            )
        except AmidProtocolError as e:
            if e.message in [
                'No Conference by that name found.',  # This conference is not running at this time.
                'No active conferences.',    # No conferences are taking place at this time.
                'No Channel by that name found in Conference.',  # Participant not found.
            ]:
                logger.debug(
                    'No participants found to kick out of meeting %s', meeting_uuid
                )
                raise NoSuchMeetingParticipant(tenant_uuid, meeting_uuid, participant_id)
            raise
        except RequestException as e:
            raise WazoAmidError(self._amid, e)
