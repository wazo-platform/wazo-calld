# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from ari.exceptions import ARINotFound
from marshmallow import ValidationError
from requests import RequestException
from wazo_calld.helpers.confd import Conference
from wazo_calld.helpers.ari_ import Channel
from wazo_calld.exceptions import (
    WazoAmidError,
)

from .exceptions import (
    NoSuchConference,
    NoSuchParticipant,
    ConferenceAlreadyRecorded,
    ConferenceNotRecorded,
    ConferenceError,
    ConferenceHasNoParticipants,
    ConferenceParticipantError,
    UserNotParticipant,
)
from .schemas import participant_schema

logger = logging.getLogger(__name__)


class ConferencesService:

    def __init__(self, amid, ari, confd):
        self._amid = amid
        self._ari = ari
        self._confd = confd

    def list_participants(self, tenant_uuid, conference_id):
        if not Conference(tenant_uuid, conference_id, self._confd).exists():
            raise NoSuchConference(tenant_uuid, conference_id)

        try:
            participant_list = self._amid.action('ConfBridgeList', {'conference': conference_id})
        except RequestException as e:
            raise WazoAmidError(self._amid, e)

        participant_list_result = participant_list.pop(0)
        if (participant_list_result['Response'] == 'Error'
           and participant_list_result['Message'] == 'No active conferences.'):
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
                'caller_id_number': participant_list_item['CallerIDNum'],
                'muted': participant_list_item['Muted'] == 'Yes',
                'join_time': participant_list_item['AnsweredTime'],
                'admin': participant_list_item['Admin'] == 'Yes',
                'language': participant_list_item['Language'],
                'call_id': participant_list_item['Uniqueid'],
                'user_uuid': Channel(participant_list_item['Uniqueid'], self._ari).user(),
            }
            try:
                participant = participant_schema.load(raw_participant)
            except ValidationError as e:
                raise ConferenceParticipantError(tenant_uuid,
                                                 conference_id,
                                                 participant_id=None,
                                                 message=str(e))
            result.append(participant)

        return result

    def user_list_participants(self, tenant_uuid, user_uuid, conference_id):
        participants = self.list_participants(tenant_uuid, conference_id)
        user_is_participant = any(participant['user_uuid'] == user_uuid for participant in participants)
        if not user_is_participant:
            raise UserNotParticipant(tenant_uuid, user_uuid, conference_id)
        return participants

    def kick_participant(self, tenant_uuid, conference_id, participant_id):
        if not Conference(tenant_uuid, conference_id, self._confd).exists():
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
            raise WazoAmidError(self._amid, e)

        response = response_items[0]
        if response['Response'] != 'Success':
            message = response['Message']
            raise ConferenceParticipantError(tenant_uuid, conference_id, participant_id, message)

    def mute_participant(self, tenant_uuid, conference_id, participant_id):
        if not Conference(tenant_uuid, conference_id, self._confd).exists():
            raise NoSuchConference(tenant_uuid, conference_id)

        participants = self.list_participants(tenant_uuid, conference_id)
        if participant_id not in [participant['id'] for participant in participants]:
            raise NoSuchParticipant(tenant_uuid, conference_id, participant_id)

        try:
            channel = self._ari.channels.get(channelId=participant_id)
        except ARINotFound:
            raise NoSuchParticipant(tenant_uuid, conference_id, participant_id)

        try:
            response_items = self._amid.action('ConfbridgeMute', {'conference': conference_id,
                                                                  'channel': channel.json['name']})
        except RequestException as e:
            raise WazoAmidError(self._amid, e)

        response = response_items[0]
        if response['Response'] != 'Success':
            message = response['Message']
            raise ConferenceParticipantError(tenant_uuid, conference_id, participant_id, message)

    def unmute_participant(self, tenant_uuid, conference_id, participant_id):
        if not Conference(tenant_uuid, conference_id, self._confd).exists():
            raise NoSuchConference(tenant_uuid, conference_id)

        participants = self.list_participants(tenant_uuid, conference_id)
        if participant_id not in [participant['id'] for participant in participants]:
            raise NoSuchParticipant(tenant_uuid, conference_id, participant_id)

        try:
            channel = self._ari.channels.get(channelId=participant_id)
        except ARINotFound:
            raise NoSuchParticipant(tenant_uuid, conference_id, participant_id)

        try:
            response_items = self._amid.action('ConfbridgeUnmute', {'conference': conference_id,
                                                                    'channel': channel.json['name']})
        except RequestException as e:
            raise WazoAmidError(self._amid, e)

        response = response_items[0]
        if response['Response'] != 'Success':
            message = response['Message']
            raise ConferenceParticipantError(tenant_uuid, conference_id, participant_id, message)

    def record(self, tenant_uuid, conference_id):
        if not Conference(tenant_uuid, conference_id, self._confd).exists():
            raise NoSuchConference(tenant_uuid, conference_id)

        participants = self.list_participants(tenant_uuid, conference_id)
        if not participants:
            raise ConferenceHasNoParticipants(tenant_uuid, conference_id)

        body = {
            'conference': conference_id,
        }
        try:
            response_items = self._amid.action('ConfbridgeStartRecord', body)
        except RequestException as e:
            raise WazoAmidError(self._amid, e)

        response = response_items[0]
        if response['Response'] != 'Success':
            message = response['Message']
            if message == 'Conference is already being recorded.':
                raise ConferenceAlreadyRecorded(tenant_uuid, conference_id)
            raise ConferenceError(tenant_uuid, conference_id, message)

    def stop_record(self, tenant_uuid, conference_id):
        if not Conference(tenant_uuid, conference_id, self._confd).exists():
            raise NoSuchConference(tenant_uuid, conference_id)

        try:
            response_items = self._amid.action('ConfbridgeStopRecord', {'conference': conference_id})
        except RequestException as e:
            raise WazoAmidError(self._amid, e)

        response = response_items[0]
        if response['Response'] != 'Success':
            message = response['Message']
            if message == 'Internal error while stopping recording.':
                raise ConferenceNotRecorded(tenant_uuid, conference_id)
            raise ConferenceError(tenant_uuid, conference_id, message)
