# -*- coding: utf-8 -*-
# Copyright 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import unittest
import uuid

from mock import Mock
from xivo_bus.resources.cti.event import UserStatusUpdateEvent

from xivo_ctid_ng.plugins.presences.services import PresencesService


class TestPresencesService(unittest.TestCase):

    def setUp(self):
        self.bus_publisher = Mock()
        self.xivo_uuid = 'xivo-uuid'
        self.service = PresencesService(self.bus_publisher)
        self.user_uuid = 'efd089b0-b803-4536-b8f0-91bab5b94604'
        self.status_name = 'available'
        self.request_body = {
            'user_uuid': self.user_uuid,
            'status_name': self.status_name,
        }

    def test_update_presence(self):
        self.service.update_presence(self.request_body)

        expected_event = UserStatusUpdateEvent(self.user_uuid, self.status_name)
        self.bus_publisher.publish.assert_called_once_with(expected_event)

    def test_update_presence_without_user_uuid(self):
        del self.request_body['user_uuid']

        self.service.update_presence(self.request_body, self.user_uuid)

        expected_event = UserStatusUpdateEvent(self.user_uuid, self.status_name)
        self.bus_publisher.publish.assert_called_once_with(expected_event)

    def test_send_message_with_user_uuid(self):
        self.service.update_presence(self.request_body)

        expected_event = UserStatusUpdateEvent(self.user_uuid, self.status_name)
        self.bus_publisher.publish.assert_called_once_with(expected_event)
