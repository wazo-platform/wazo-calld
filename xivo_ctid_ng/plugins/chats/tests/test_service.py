# -*- coding: utf-8 -*-
# Copyright 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import unittest
import uuid

from mock import Mock
from xivo_bus.resources.chat.event import ChatMessageEvent

from xivo_ctid_ng.plugins.chats.services import ChatsService


class TestChatsService(unittest.TestCase):

    def setUp(self):
        self.bus_publisher = Mock()
        self.xivo_uuid = 'xivo-uuid'
        self.service = ChatsService(self.bus_publisher, self.xivo_uuid)
        self.alias = 'alice'
        self.msg = 'hello'
        self.from_ = uuid.uuid4()
        self.to = uuid.uuid4()
        self.to_xivo_uuid = uuid.uuid4()
        self.request_body = {
            'alias': self.alias,
            'from': self.from_,
            'to': self.to,
            'to_xivo_uuid': self.to_xivo_uuid,
            'msg': self.msg,
        }

    def test_send_message(self):
        self.service.send_message(self.request_body)

        expected_event = ChatMessageEvent((self.xivo_uuid, str(self.from_)),
                                          (str(self.to_xivo_uuid), str(self.to)),
                                          self.alias,
                                          self.msg)
        self.bus_publisher.publish.assert_called_once_with(expected_event)

    def test_send_message_without_to_xivo_uuid(self):
        del self.request_body['to_xivo_uuid']

        self.service.send_message(self.request_body)

        expected_event = ChatMessageEvent((self.xivo_uuid, str(self.from_)),
                                          (self.xivo_uuid, str(self.to)),
                                          self.alias,
                                          self.msg)
        self.bus_publisher.publish.assert_called_once_with(expected_event)

    def test_send_message_with_user_uuid(self):
        user_uuid = 'user-uuid'

        self.service.send_message(self.request_body, user_uuid)

        expected_event = ChatMessageEvent((self.xivo_uuid, user_uuid),
                                          (str(self.to_xivo_uuid), str(self.to)),
                                          self.alias,
                                          self.msg)
        self.bus_publisher.publish.assert_called_once_with(expected_event)
