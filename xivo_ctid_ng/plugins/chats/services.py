# -*- coding: utf-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests
from requests import RequestException
from xivo_ctid_ng.core.exceptions import APIException

chat_contexts = {}


class MongooseIMUnreachable(APIException):

    def __init__(self, xivo_uuid, error):
        super(MongooseIMUnreachable, self).__init__(
            status_code=503,
            message='mongooseim server unreachable',
            error_id='mongooseim-unreachable',
            details={
                'xivo_uuid': xivo_uuid,
                'original_error': str(error),
                'service': 'xivo-ctid-ng',
            }
        )


class MongooseIMException(APIException):

    def __init__(self, xivo_uuid, error):
        super(MongooseIMException, self).__init__(
            status_code=503,
            message='mongooseim error',
            error_id='mongooseim-exception',
            details={
                'xivo_uuid': xivo_uuid,
                'original_error': str(error),
                'service': 'xivo-ctid-ng',
            }
        )


class ChatsService(object):

    def __init__(self, xivo_uuid, mongooseim_config):
        self._xivo_uuid = xivo_uuid
        self.mongooseim_config = mongooseim_config

    def send_message(self, request_body, user_uuid=None):
        _, from_ = self._build_from(request_body, user_uuid)
        to_xivo_uuid, to = self._build_to(request_body)
        alias = request_body['alias']
        msg = request_body['msg']
        msg = msg.replace('&', '#26')

        self._save_context(from_, to, to_xivo_uuid, alias)
        self._send_mongooseim_message(from_, to, msg)

    def _build_from(self, request_body, token_user_uuid):
        user_uuid = token_user_uuid or str(request_body['from'])
        return (self._xivo_uuid, user_uuid)

    def _build_to(self, request_body):
        xivo_uuid = str(request_body.get('to_xivo_uuid', self._xivo_uuid))
        user_uuid = str(request_body['to'])
        return (xivo_uuid, user_uuid)

    def _save_context(self, from_, to, to_xivo_uuid, alias):
        chat_contexts['{}-{}'.format(from_, to)] = {'to_xivo_uuid': to_xivo_uuid,
                                                    'alias': alias}

    def _send_mongooseim_message(self, from_, to, msg):
        url = 'http://{}:{}/api/messages'.format(self.mongooseim_config['host'],
                                                 self.mongooseim_config['port'])
        bare_jid = '{}@localhost'
        body = {'caller': bare_jid.format(from_),
                'to': bare_jid.format(to),
                'body': msg}
        try:
            response = requests.post(url, json=body)
        except RequestException as e:
            raise MongooseIMUnreachable(self._xivo_uuid, e)

        if response.status_code != 204:
            raise MongooseIMException(self._xivo_uuid,
                                      '{}-{}'.format(response.status_code, response.reason))
