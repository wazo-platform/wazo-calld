# -*- coding: utf-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from datetime import datetime
from requests import RequestException, HTTPError
from xivo_ctid_ng.core.exceptions import APIException


class MongooseIMUnreachable(APIException):

    def __init__(self, xivo_uuid, error):
        super(MongooseIMUnreachable, self).__init__(
            status_code=503,
            message='mongooseim server unreachable',
            error_id='mongooseim-unreachable',
            resource='chats',
            details={
                'xivo_uuid': xivo_uuid,
                'original_error': str(error),
                'service': 'xivo-ctid-ng',
            }
        )


class MongooseIMException(APIException):

    def __init__(self, xivo_uuid, status_code, error):
        super(MongooseIMException, self).__init__(
            status_code=503,
            message='mongooseim error',
            error_id='mongooseim-exception',
            resource='chats',
            details={
                'xivo_uuid': xivo_uuid,
                'original_error': str(error),
                'original_status_code': status_code,
                'service': 'xivo-ctid-ng',
            }
        )


class ChatsService(object):

    def __init__(self, xivo_uuid, mongooseim_client, contexts):
        self._xivo_uuid = xivo_uuid
        self.contexts = contexts
        self.mongooseim_client = mongooseim_client

    def get_history(self, user_uuid, args):
        mongooseim_history = self._get_mongooseim_history(user_uuid, args)
        history = self._convert_history_result(mongooseim_history,
                                               user_uuid,
                                               args.get('participant_user_uuid'),
                                               args.get('participant_server_uuid'))

        return {'items': history}

    def _get_mongooseim_history(self, user_uuid, args):
        participant_user = args.get('participant_user_uuid')
        participant_server = args.get('participant_server_uuid', self._xivo_uuid)
        limit = args.get('limit')

        user_jid = self._build_jid(self._xivo_uuid, user_uuid)
        try:
            if participant_user:
                participant_jid = self._build_jid(participant_server, participant_user)
                result = self.mongooseim_client.get_user_history_with_participant(user_jid,
                                                                                  participant_jid,
                                                                                  limit)
            else:
                result = self.mongooseim_client.get_user_history(user_jid, limit)
        except HTTPError as e:
            raise MongooseIMException(self._xivo_uuid, e.response.status_code, e.response.reason)
        except RequestException as e:
            raise MongooseIMUnreachable(self._xivo_uuid, e)

        return result

    def _convert_history_result(self, history, user_uuid, participant_user=None, participant_server=None):
        result = []
        if participant_server and not participant_user:
            participant_server = None

        if not participant_server and participant_user:
            participant_server = self._xivo_uuid

        for entry in history:
            sender, domain = entry['sender'].split('@', 1)
            domain = domain if domain != 'localhost' else self._xivo_uuid
            if sender == user_uuid:
                direction = 'sent'
                source_user_uuid = user_uuid
                source_server_uuid = self._xivo_uuid
                destination_user_uuid = participant_user
                destination_server_uuid = participant_server
            else:
                direction = 'received'
                source_user_uuid = sender
                source_server_uuid = domain
                destination_user_uuid = user_uuid
                destination_server_uuid = self._xivo_uuid

            result.append({'msg': entry.get('body'),
                           'source_user_uuid': source_user_uuid,
                           'source_server_uuid': source_server_uuid,
                           'destination_user_uuid': destination_user_uuid,
                           'destination_server_uuid': destination_server_uuid,
                           'date': datetime.utcfromtimestamp(int(entry['timestamp'])),
                           'direction': direction})
        return result

    def send_message(self, request_body, user_uuid=None):
        from_xivo_uuid, from_ = self._build_from(request_body, user_uuid)
        to_xivo_uuid, to = self._build_to(request_body)
        alias = request_body['alias']
        msg = request_body['msg']
        self.contexts.add(from_, to, to_xivo_uuid=to_xivo_uuid, alias=alias)

        from_jid = self._build_jid(from_xivo_uuid, from_)
        to_jid = self._build_jid(to_xivo_uuid, to)
        try:
            self.mongooseim_client.send_message(from_jid, to_jid, msg)
        except HTTPError as e:
            raise MongooseIMException(self._xivo_uuid, e.response.status_code, e.response.reason)
        except RequestException as e:
            raise MongooseIMUnreachable(self._xivo_uuid, e)

    def _build_from(self, request_body, token_user_uuid):
        user_uuid = token_user_uuid or str(request_body['from'])
        return (self._xivo_uuid, user_uuid)

    def _build_to(self, request_body):
        xivo_uuid = str(request_body.get('to_xivo_uuid', self._xivo_uuid))
        user_uuid = str(request_body['to'])
        return (xivo_uuid, user_uuid)

    def _build_jid(self, domain, username):
        domain = 'localhost' if str(domain) == str(self._xivo_uuid) else domain
        return '{}@{}'.format(username, domain)
