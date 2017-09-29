# -*- coding: utf-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import datetime as dt
import unittest
import uuid

from requests import RequestException, HTTPError
from hamcrest import (
    assert_that,
    calling,
    contains,
    equal_to,
    has_entries,
    raises,
)
from mock import Mock

from ..contexts import ChatsContexts
from ..services import (
    ChatsService,
    MongooseIMException,
    MongooseIMUnreachable,
)


class TestChatsService(unittest.TestCase):

    def setUp(self):
        self.xivo_uuid = 'xivo-uuid'
        self.mongooseim_client = Mock()
        self.bus_publisher = Mock()
        self.service = ChatsService(self.xivo_uuid, self.mongooseim_client, ChatsContexts, self.bus_publisher)
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

    def test_send_message(self):
        self.service.send_message(self.request_body)

        from_jid = '{}@localhost'.format(self.request_body['from'])
        to_jid = '{}@{}'.format(self.request_body['to'], self.request_body['to_xivo_uuid'])
        msg = self.request_body['msg']
        self.mongooseim_client.send_message.assert_called_once_with(from_jid, to_jid, msg)

    def test_send_message_then_context_saved(self):
        self.service.send_message(self.request_body)

        context = ChatsContexts.get(self.from_, self.to)
        assert_that(context, equal_to({'to_xivo_uuid': self.to_xivo_uuid, 'alias': self.alias}))

    def test_send_message_without_to_xivo_uuid(self):
        del self.request_body['to_xivo_uuid']

        self.service.send_message(self.request_body)

        context = ChatsContexts.get(self.from_, self.to)
        assert_that(context, equal_to({'to_xivo_uuid': self.xivo_uuid, 'alias': self.alias}))

    def test_send_message_without_from(self):
        del self.request_body['from']

        self.service.send_message(self.request_body, 'user-uuid')

        from_jid = '{}@localhost'.format('user-uuid')
        to_jid = '{}@{}'.format(self.request_body['to'], self.request_body['to_xivo_uuid'])
        msg = self.request_body['msg']
        self.mongooseim_client.send_message.assert_called_once_with(from_jid, to_jid, msg)

    def test_send_message_with_same_to_xivo_uuid(self):
        self.request_body['to_xivo_uuid'] = self.xivo_uuid

        self.service.send_message(self.request_body)

        from_jid = '{}@localhost'.format(self.request_body['from'])
        to_jid = '{}@localhost'.format(self.request_body['to'])
        msg = self.request_body['msg']
        self.mongooseim_client.send_message.assert_called_once_with(from_jid, to_jid, msg)

    def test_send_message_when_unreachable_mongooseim(self):
        self.mongooseim_client.send_message.side_effect = RequestException()

        assert_that(calling(self.service.send_message).with_args(self.request_body),
                    raises(MongooseIMUnreachable))

    def test_send_message_when_mongooseim_return_500(self):
        self.mongooseim_client.send_message.side_effect = HTTPError(response=Mock())

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

    def test_get_history_when_unreachable_mongooseim(self):
        self.mongooseim_client.get_user_history.side_effect = RequestException()

        assert_that(calling(self.service.get_history).with_args(self.from_, {}),
                    raises(MongooseIMUnreachable))

    def test_get_history_when_mongooseim_return_500(self):
        self.mongooseim_client.get_user_history.side_effect = HTTPError(response=Mock())

        assert_that(calling(self.service.get_history).with_args(self.from_, {}),
                    raises(MongooseIMException))
