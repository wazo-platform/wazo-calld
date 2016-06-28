# -*- coding: utf-8 -*-
# Copyright 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import unittest

from mock import Mock
from xivo_bus.resources.cti.event import UserStatusUpdateEvent

from xivo_ctid_ng.plugins.presences.services import PresencesService


class TestPresencesService(unittest.TestCase):

    def setUp(self):
        self.bus_publisher = Mock()
        self.xivo_uuid = 'xivo-uuid'
        ctid_client = Mock()
        ctid_config = dict()
        self.service = PresencesService(self.bus_publisher, ctid_client, ctid_config)
        self.user_uuid = 'efd089b0-b803-4536-b8f0-91bab5b94604'
        self.presence = 'available'

    def test_update_presence(self):
        self.service.update_presence(self.user_uuid, self.presence)

        expected_event = UserStatusUpdateEvent(self.user_uuid, self.presence)
        self.bus_publisher.publish.assert_called_once_with(expected_event)
