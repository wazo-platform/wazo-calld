# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from ari.exceptions import ARINotFound
from marshmallow import ValidationError
from requests import RequestException
from xivo_ctid_ng.exceptions import (
    XiVOAmidError,
    XiVOConfdUnreachable,
)

from .exceptions import (
    NoSuchConference,
    NoSuchParticipant,
    ConferenceParticipantError,
)
from .schemas import participant_schema

logger = logging.getLogger(__name__)


class ConferencesService:

    def __init__(self, amid, ari, confd):
        self._amid = amid
        self._ari = ari
        self._confd = confd

    def list_participants(self, tenant_uuid, conference_id):
        try:
            conferences = self._confd.conferences.list(tenant_uuid=tenant_uuid, recurse=True)['items']
        except RequestException as e:
            raise XiVOConfdUnreachable(self._confd, e)
        if conference_id not in (conference['id'] for conference in conferences):
            raise NoSuchConference(tenant_uuid, conference_id)

        try:
            participant_list = self._amid.action('ConfBridgeList', {'conference': conference_id})
        except RequestException as e:
            raise XiVOAmidError(self._amid, e)

        participant_list_result = participant_list.pop(0)
        if (participant_list_result['Response'] == 'Error' and
                participant_list_result['Message'] == 'No active conferences.'):
            return []

        if participant_list_result['Response'] != 'Success':
            message = participant_list_result['Message']
            raise ConferenceParticipantError(tenant_uuid,
                                             conference_id,
                                             participant_id=None,
                                             message=message)

        result = []
        for participant_list_item in participant_list:
            if participant_list_item['Event'] != 'ConfbridgeList':
                continue

            raw_participant = {
                'id': participant_list_item['Uniqueid'],
                'caller_id_name': participant_list_item['CallerIDName'],
                'caller_id_num': participant_list_item['CallerIDNum'],
                'muted': participant_list_item['Muted'] == 'Yes',
                'join_time': participant_list_item['AnsweredTime'],
                'admin': participant_list_item['Admin'] == 'Yes',
                'language': participant_list_item['Language'],
                'call_id': participant_list_item['Uniqueid'],
            }
            try:
                participant = participant_schema.load(raw_participant).data
            except ValidationError as e:
                raise ConferenceParticipantError(tenant_uuid,
                                                 conference_id,
                                                 participant_id=None,
                                                 message=str(e))
            result.append(participant)

        return result

    def kick_participant(self, tenant_uuid, conference_id, participant_id):
        try:
            conferences = self._confd.conferences.list(tenant_uuid=tenant_uuid, recurse=True)['items']
        except RequestException as e:
            raise XiVOConfdUnreachable(self._confd, e)

        if conference_id not in (conference['id'] for conference in conferences):
            raise NoSuchConference(tenant_uuid, conference_id)

        participants = self.list_participants(tenant_uuid, conference_id)
        if participant_id not in [participant['id'] for participant in participants]:
            raise NoSuchParticipant(tenant_uuid, conference_id, participant_id)

        try:
            channel = self._ari.channels.get(channelId=participant_id)
        except ARINotFound:
            raise NoSuchParticipant(tenant_uuid, conference_id, participant_id)

        try:
            response_items = self._amid.action('ConfbridgeKick', {'conference': conference_id,
                                                                  'channel': channel.json['name']})
        except RequestException as e:
            raise XiVOAmidError(self._amid, e)

        response = response_items[0]
        if response['Response'] != 'Success':
            message = response['Message']
            raise ConferenceParticipantError(tenant_uuid, conference_id, participant_id, message)
