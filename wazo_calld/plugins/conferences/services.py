# Copyright 2018-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from ari.exceptions import ARINotFound
from marshmallow import ValidationError
from requests import RequestException
from wazo_amid_client.exceptions import AmidProtocolError
from wazo_calld.plugin_helpers.confd import Conference
from wazo_calld.plugin_helpers.ari_ import Channel
from wazo_calld.plugin_helpers.exceptions import (
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
            participant_list = self._amid.action('ConfBridgeList', {'conference': f'wazo-conference-{conference_id}'})
        except AmidProtocolError as e:
            no_conf_msg = [
                'No active conferences.',  # No conferences are taking place at this time.
                'No Conference by that name found.',  # This conference is not running at this time.
            ]
            if e.message in no_conf_msg:
                return []
            raise ConferenceParticipantError(
                tenant_uuid,
                conference_id,
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
            self._amid.action(
                'ConfbridgeKick',
                {'conference': f'wazo-conference-{conference_id}', 'channel': channel.json['name']},
            )
        except AmidProtocolError as e:
            raise ConferenceParticipantError(tenant_uuid, conference_id, participant_id, e.message)
        except RequestException as e:
            raise WazoAmidError(self._amid, e)

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
            self._amid.action(
                'ConfbridgeMute',
                {'conference': f'wazo-conference-{conference_id}', 'channel': channel.json['name']},
            )
        except AmidProtocolError as e:
            raise ConferenceParticipantError(tenant_uuid, conference_id, participant_id, e.message)
        except RequestException as e:
            raise WazoAmidError(self._amid, e)

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
            self._amid.action(
                'ConfbridgeUnmute',
                {'conference': f'wazo-conference-{conference_id}', 'channel': channel.json['name']},
            )
        except AmidProtocolError as e:
            raise ConferenceParticipantError(tenant_uuid, conference_id, participant_id, e.message)
        except RequestException as e:
            raise WazoAmidError(self._amid, e)

    def record(self, tenant_uuid, conference_id):
        if not Conference(tenant_uuid, conference_id, self._confd).exists():
            raise NoSuchConference(tenant_uuid, conference_id)

        participants = self.list_participants(tenant_uuid, conference_id)
        if not participants:
            raise ConferenceHasNoParticipants(tenant_uuid, conference_id)

        body = {
            'conference': f'wazo-conference-{conference_id}',
        }
        try:
            self._amid.action('ConfbridgeStartRecord', body)
        except AmidProtocolError as e:
            if e.message == 'Conference is already being recorded.':
                raise ConferenceAlreadyRecorded(tenant_uuid, conference_id)
            raise ConferenceError(tenant_uuid, conference_id, e.message)
        except RequestException as e:
            raise WazoAmidError(self._amid, e)

    def stop_record(self, tenant_uuid, conference_id):
        if not Conference(tenant_uuid, conference_id, self._confd).exists():
            raise NoSuchConference(tenant_uuid, conference_id)

        try:
            self._amid.action('ConfbridgeStopRecord', {'conference': f'wazo-conference-{conference_id}'})
        except AmidProtocolError as e:
            if e.message == 'Internal error while stopping recording.':
                raise ConferenceNotRecorded(tenant_uuid, conference_id)
            raise ConferenceError(tenant_uuid, conference_id, e.message)
        except RequestException as e:
            raise WazoAmidError(self._amid, e)
