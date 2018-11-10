# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import unittest

from mock import Mock
from xivo_bus.resources.chat.event import ChatMessageEvent
from xivo_bus.resources.chat.event import ChatMessageReceived

from xivo_ctid_ng.plugins.chats.contexts import ChatsContexts
from ..services import MessageCallbackService


class TestMessageCallbackService(unittest.TestCase):

    def setUp(self):
        self.bus_publisher = Mock()
        self.xivo_uuid = 'xivo-uuid'
        self.service = MessageCallbackService(self.bus_publisher, self.xivo_uuid, ChatsContexts)
        self.alias = 'GhostBuster'
        self.to_xivo_uuid = 'other-xivo-uuid'
        self.message = 'hello'
        self.author = 'Author'
        self.receiver = 'Receiver'
        ChatsContexts.add(self.author, self.receiver, to_xivo_uuid=self.to_xivo_uuid, alias=self.alias)
        self.request_body = {
            'author': self.author,
            'receiver': self.receiver,
            'message': self.message,
        }

    def test_send_message(self):
        expected_event_legacy = ChatMessageEvent((self.xivo_uuid, self.author),
                                                 (self.to_xivo_uuid, self.receiver),
                                                 self.alias,
                                                 self.message)
        expected_event = ChatMessageReceived((self.xivo_uuid, self.author),
                                             (self.to_xivo_uuid, self.receiver),
                                             self.alias,
                                             self.message)
        expected_headers = {
            'user_uuid:{uuid}'.format(uuid=self.receiver): True,
        }

        self.service.send_message(self.request_body)

        self.bus_publisher.publish.assert_any_call(expected_event_legacy)
        self.bus_publisher.publish.assert_any_call(expected_event, headers=expected_headers)
