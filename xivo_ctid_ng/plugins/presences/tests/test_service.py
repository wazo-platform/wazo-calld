# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# Copyright (C) 2016 Proformatique, Inc.
# SPDX-License-Identifier: GPL-3.0+

import unittest

from hamcrest import assert_that, contains, equal_to
from mock import Mock, patch, sentinel as s
from xivo_bus.resources.cti.event import UserStatusUpdateEvent

from ..services import UserPresencesService


class TestPresencesService(unittest.TestCase):

    def setUp(self):
        self.bus_publisher = Mock()
        self.xivo_uuid = 'xivo-uuid'
        self.ctid_client = Mock()
        ctid_config = dict()
        self.service = UserPresencesService(self.bus_publisher,
                                            self.ctid_client,
                                            ctid_config,
                                            s.local_xivo_uuid,
                                            Mock())
        self.user_uuid = 'efd089b0-b803-4536-b8f0-91bab5b94604'
        self.presence = 'available'

    def test_update_presence(self):
        self.service.update_presence(self.user_uuid, self.presence)

        expected_event = UserStatusUpdateEvent(self.user_uuid, self.presence)
        self.bus_publisher.publish.assert_called_once_with(expected_event)

    def test_get_local_presence(self):
        self.ctid_client.users.get.return_value = {'origin_uuid': s.origin_uuid,
                                                   'presence': s.presence}

        response = self.service.get_local_presence(s.user_uuid)

        assert_that(response, contains(s.origin_uuid, s.presence))
        self.ctid_client.users.get.assert_called_once_with(s.user_uuid)

    def test_get_presence_with_local_xivo_uuid(self):
        with patch.object(self.service, 'get_local_presence') as get_local_presence:
            response = self.service.get_presence(s.local_xivo_uuid, s.user_uuid)

        assert_that(response, equal_to(get_local_presence.return_value))
        get_local_presence.assert_called_once_with(s.user_uuid)

    def test_get_presence_with_remote_xivo_uuid(self):
        with patch.object(self.service, 'get_remote_presence') as get_remote_presence:
            response = self.service.get_presence(s.remote_xivo_uuid, s.user_uuid)

        assert_that(response, equal_to(get_remote_presence.return_value))
        get_remote_presence.assert_called_once_with(s.remote_xivo_uuid, s.user_uuid)

    def test_get_presence_xivo_uuid_is_none(self):
        with patch.object(self.service, 'get_local_presence') as get_local_presence:
            response = self.service.get_presence(None, s.user_uuid)

        assert_that(response, equal_to(get_local_presence.return_value))
        get_local_presence.assert_called_once_with(s.user_uuid)
