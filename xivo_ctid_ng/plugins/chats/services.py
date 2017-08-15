# -*- coding: utf-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests

from datetime import datetime
from requests import RequestException
from requests.utils import quote
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

    def __init__(self, xivo_uuid, mongooseim_config, contexts):
        self._xivo_uuid = xivo_uuid
        self.mongooseim_config = mongooseim_config
        self.contexts = contexts

    def get_history(self, user_uuid, args):
        mongooseim_history = self._get_mongooseim_history(user_uuid, args)
        history = self._convert_history_result(mongooseim_history,
                                               user_uuid,
                                               args.get('participant_user_uuid'),
                                               args.get('participant_server_uuid'))

        return {'items': history}

    def _get_mongooseim_history(self, user_uuid, args):
        participant_user = args.get('participant_user_uuid')
        participant_server = args.get('participant_server_uuid', 'localhost')
        limit = args.get('limit')

        if participant_user:
            url = self._build_history_url_with_participant(user_uuid, participant_user, participant_server)
        else:
            url = self._build_history_url(user_uuid)

        params = {}
        if limit:
            params['limit'] = limit
        try:
            response = requests.get(url, params=params)
        except RequestException as e:
            raise MongooseIMUnreachable(self._xivo_uuid, e)

        if response.status_code != 200:
            raise MongooseIMException(self._xivo_uuid, response.status_code, response.reason)

        return response.json()

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

    def _build_history_url(self, user_uuid):
        user_jid = self._build_escaped_jid(user_uuid, 'localhost')
        return 'http://{}:{}/api/messages/{}'.format(self.mongooseim_config['host'],
                                                     self.mongooseim_config['port'],
                                                     user_jid)

    def _build_history_url_with_participant(self, user_uuid, participant_user, participant_server):
        user_jid = self._build_remote_jid(self._xivo_uuid, user_uuid)
        participant_jid = self._build_remote_jid(participant_server, participant_user)
        return 'http://{}:{}/api/messages/{}/{}'.format(self.mongooseim_config['host'],
                                                        self.mongooseim_config['port'],
                                                        quote(user_jid),
                                                        quote(participant_jid))

    def _build_escaped_jid(self, username, server):
        return '{}%40{}'.format(username, server)

    def send_message(self, request_body, user_uuid=None):
        _, from_ = self._build_from(request_body, user_uuid)
        to_xivo_uuid, to = self._build_to(request_body)
        alias = request_body['alias']
        msg = self._escape_buggy_symbols_for_mongooseim(request_body['msg'])

        self.contexts.add(from_, to, to_xivo_uuid=to_xivo_uuid, alias=alias)
        self._send_mongooseim_message(from_, to_xivo_uuid, to,  msg)

    def _escape_buggy_symbols_for_mongooseim(self, msg):
        return msg.replace('&', '#26')

    def _build_from(self, request_body, token_user_uuid):
        user_uuid = token_user_uuid or str(request_body['from'])
        return (self._xivo_uuid, user_uuid)

    def _build_to(self, request_body):
        xivo_uuid = str(request_body.get('to_xivo_uuid', self._xivo_uuid))
        user_uuid = str(request_body['to'])
        return (xivo_uuid, user_uuid)

    def _send_mongooseim_message(self, from_, to_domain, to, msg):
        url = 'http://{}:{}/api/messages'.format(self.mongooseim_config['host'],
                                                 self.mongooseim_config['port'])
        bare_jid = '{}@localhost'
        body = {'caller': bare_jid.format(from_),
                'to': self._build_remote_jid(to_domain, to),
                'body': msg}
        try:
            response = requests.post(url, json=body)
        except RequestException as e:
            raise MongooseIMUnreachable(self._xivo_uuid, e)

        if response.status_code != 204:
            raise MongooseIMException(self._xivo_uuid, response.status_code, response.reason)

    def _build_remote_jid(self, to_domain, to):
        domain = 'localhost' if str(to_domain) == str(self._xivo_uuid) else to_domain
        return '{}@{}'.format(to, domain)
