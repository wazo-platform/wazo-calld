# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import unittest

from mock import Mock
from xivo_bus.resources.chat.event import ChatMessageEvent

from ..services import MessageCallbackService


class TestMessageCallbackService(unittest.TestCase):

    def setUp(self):
        self.bus_publisher = Mock()
        self.xivo_uuid = 'xivo-uuid'
        self.service = MessageCallbackService(self.bus_publisher, self.xivo_uuid)
        self.message = 'hello'
        self.alias = 'GhostBuster'
        self.to_xivo_uuid = self.xivo_uuid
        self.author = 'Author'
        self.receiver = 'Receiver'
        self.request_body = {
            'author': self.author,
            'receiver': self.receiver,
            'message': self.message,
        }

    def test_send_message(self):
        self.service.send_message(self.request_body)

        expected_event = ChatMessageEvent((self.xivo_uuid, self.author),
                                          (self.to_xivo_uuid, self.receiver),
                                          self.alias,
                                          self.message)
        self.bus_publisher.publish.assert_called_once_with(expected_event)
