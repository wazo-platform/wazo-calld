# -*- coding: utf-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import datetime as dt
import unittest
import uuid

from requests import RequestException
from hamcrest import (
    assert_that,
    calling,
    contains,
    equal_to,
    has_entries,
    raises,
)
from mock import Mock, patch

from ..contexts import ChatsContexts
from ..services import (
    ChatsService,
    MongooseIMException,
    MongooseIMUnreachable,
)


class TestChatsService(unittest.TestCase):

    def setUp(self):
        self.xivo_uuid = 'xivo-uuid'
        self.mongooseim_config = {'host': 'localhost', 'port': 8088}
        self.service = ChatsService(self.xivo_uuid, self.mongooseim_config, ChatsContexts)
        self.alias = 'alice'
        self.msg = 'hello'
        self.from_ = str(uuid.uuid4())
        self.to = str(uuid.uuid4())
        self.to_xivo_uuid = str(uuid.uuid4())
        self.request_body = {
            'alias': self.alias,
            'from': self.from_,
            'to': self.to,
            'to_xivo_uuid': self.to_xivo_uuid,
            'msg': self.msg,
        }
        self.expected_url = 'http://{}:{}/api/messages'.format(self.mongooseim_config['host'],
                                                               self.mongooseim_config['port'])

    @patch('xivo_ctid_ng.plugins.chats.services.requests')
    def test_send_message(self, requests):
        requests.post.return_value = Mock(status_code=204)

        self.service.send_message(self.request_body)

        expected_body = self.expected_body(self.request_body['from'],
                                           self.request_body['to'],
                                           self.request_body['msg'])
        requests.post.assert_called_once_with(self.expected_url, json=expected_body)

    @patch('xivo_ctid_ng.plugins.chats.services.requests')
    def test_send_message_with_ampersand(self, requests):
        self.request_body['msg'] = 'Ampersand&Power'
        requests.post.return_value = Mock(status_code=204)

        self.service.send_message(self.request_body)

        expected_body = self.expected_body(self.request_body['from'],
                                           self.request_body['to'],
                                           'Ampersand#26Power')
        requests.post.assert_called_once_with(self.expected_url, json=expected_body)

    @patch('xivo_ctid_ng.plugins.chats.services.requests')
    def test_send_message_then_context_saved(self, requests):
        requests.post.return_value = Mock(status_code=204)

        self.service.send_message(self.request_body)

        context = ChatsContexts.get(self.from_, self.to)
        assert_that(context, equal_to({'to_xivo_uuid': self.to_xivo_uuid, 'alias': self.alias}))

    @patch('xivo_ctid_ng.plugins.chats.services.requests')
    def test_send_message_without_to_xivo_uuid(self, requests):
        del self.request_body['to_xivo_uuid']
        requests.post.return_value = Mock(status_code=204)

        self.service.send_message(self.request_body)

        context = ChatsContexts.get(self.from_, self.to)
        assert_that(context, equal_to({'to_xivo_uuid': self.xivo_uuid, 'alias': self.alias}))

    @patch('xivo_ctid_ng.plugins.chats.services.requests')
    def test_send_message_without_from(self, requests):
        del self.request_body['from']
        requests.post.return_value = Mock(status_code=204)

        self.service.send_message(self.request_body, 'user-uuid')

        expected_body = self.expected_body('user-uuid',
                                           self.request_body['to'],
                                           self.request_body['msg'])
        requests.post.assert_called_once_with(self.expected_url, json=expected_body)

    @patch('xivo_ctid_ng.plugins.chats.services.requests')
    def test_send_message_with_same_to_xivo_uuid(self, requests):
        requests.post.return_value = Mock(status_code=204)
        request_body = self.request_body
        request_body['to_xivo_uuid'] = self.xivo_uuid

        self.service.send_message(request_body)

        expected_body = self.expected_body(self.request_body['from'],
                                           self.request_body['to'],
                                           self.request_body['msg'],
                                           request_body['to_xivo_uuid'])
        requests.post.assert_called_once_with(self.expected_url, json=expected_body)

    def expected_body(self, from_, to, msg, to_xivo_uuid=None):
        if not to_xivo_uuid:
            to_xivo_uuid = self.to_xivo_uuid
        return {'caller': '{}@localhost'.format(from_),
                'to': '{}@{}'.format(to, 'localhost' if to_xivo_uuid == self.xivo_uuid else to_xivo_uuid),
                'body': msg}

    @patch('xivo_ctid_ng.plugins.chats.services.requests')
    def test_send_message_when_unreachable_mongooseim(self, requests):
        requests.post.side_effect = RequestException()

        assert_that(calling(self.service.send_message).with_args(self.request_body),
                    raises(MongooseIMUnreachable))

    @patch('xivo_ctid_ng.plugins.chats.services.requests')
    def test_send_message_when_mongooseim_return_500(self, requests):
        requests.post.return_value = Mock(status_code=500)

        assert_that(calling(self.service.send_message).with_args(self.request_body),
                    raises(MongooseIMException))

    def test_convert_history_result_without_participant(self):
        user2 = str(uuid.uuid4())
        server2 = str(uuid.uuid4())
        user3 = str(uuid.uuid4())
        history = [{'sender': '{}@localhost'.format(self.from_), 'msg': 'hi', 'timestamp': '1502462596'},
                   {'sender': '{}@{}'.format(user2, server2), 'msg': 'hello', 'timestamp': '1502462597'},
                   {'sender': '{}@localhost'.format(user3), 'msg': 'hi', 'timestamp': '1502462598'}]
        result = self.service._convert_history_result(history, self.from_)

        assert_that(result, contains(
            has_entries(source_user_uuid=self.from_,
                        source_server_uuid=self.xivo_uuid,
                        destination_user_uuid=None,
                        destination_server_uuid=None,
                        direction='sent',
                        date=dt.datetime(2017, 8, 11, 14, 43, 16)),
            has_entries(source_user_uuid=user2,
                        source_server_uuid=server2,
                        destination_user_uuid=self.from_,
                        destination_server_uuid=self.xivo_uuid,
                        direction='received',
                        date=dt.datetime(2017, 8, 11, 14, 43, 17)),
            has_entries(source_user_uuid=user3,
                        source_server_uuid=self.xivo_uuid,
                        destination_user_uuid=self.from_,
                        destination_server_uuid=self.xivo_uuid,
                        direction='received',
                        date=dt.datetime(2017, 8, 11, 14, 43, 18)),
        ))

    def test_convert_history_result_wit_participant_server_only(self):
        server2 = str(uuid.uuid4())
        history = [{'sender': '{}@localhost'.format(self.from_), 'msg': 'hi', 'timestamp': '1502462596'}]
        result = self.service._convert_history_result(history, self.from_, participant_server=server2)

        assert_that(result, contains(
            has_entries(source_user_uuid=self.from_,
                        source_server_uuid=self.xivo_uuid,
                        destination_user_uuid=None,
                        destination_server_uuid=None,
                        direction='sent')
        ))

    def test_convert_history_result_wit_participant_user_only(self):
        user2 = str(uuid.uuid4())
        history = [{'sender': '{}@localhost'.format(self.from_), 'msg': 'hi', 'timestamp': '1502462596'}]
        result = self.service._convert_history_result(history, self.from_, participant_user=user2)

        assert_that(result, contains(
            has_entries(source_user_uuid=self.from_,
                        source_server_uuid=self.xivo_uuid,
                        destination_user_uuid=user2,
                        destination_server_uuid=self.xivo_uuid,
                        direction='sent')
        ))

    def test_convert_history_result_with_participant(self):
        user2 = str(uuid.uuid4())
        server2 = str(uuid.uuid4())
        history = [{'sender': '{}@localhost'.format(self.from_), 'msg': 'hi', 'timestamp': '1502462596'}]
        result = self.service._convert_history_result(history, self.from_,
                                                      participant_user=user2,
                                                      participant_server=server2)

        assert_that(result, contains(
            has_entries(source_user_uuid=self.from_,
                        source_server_uuid=self.xivo_uuid,
                        destination_user_uuid=user2,
                        destination_server_uuid=server2,
                        direction='sent')
        ))

    @patch('xivo_ctid_ng.plugins.chats.services.requests')
    def test_get_history_when_unreachable_mongooseim(self, requests):
        requests.get.side_effect = RequestException()

        assert_that(calling(self.service.get_history).with_args(self.from_, {}),
                    raises(MongooseIMUnreachable))

    @patch('xivo_ctid_ng.plugins.chats.services.requests')
    def test_get_history_when_mongooseim_return_500(self, requests):
        requests.get.return_value = Mock(status_code=500)

        assert_that(calling(self.service.get_history).with_args(self.from_, {}),
                    raises(MongooseIMException))
