# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import unittest

from hamcrest import assert_that, contains, equal_to
from mock import Mock, patch, sentinel as s

from ..services import UserPresencesService


class TestPresencesService(unittest.TestCase):

    def setUp(self):
        self.bus_publisher = Mock()
        self.xivo_uuid = 'xivo-uuid'
        self.websocketd_client = Mock()
        self.service = UserPresencesService(self.bus_publisher,
                                            self.websocketd_client,
                                            s.local_xivo_uuid,
                                            Mock())
        self.user_uuid = 'efd089b0-b803-4536-b8f0-91bab5b94604'
        self.presence = 'available'

    def test_get_local_presence(self):
        self.websocketd_client.get_presence.return_value = s.presence

        response = self.service.get_local_presence(s.user_uuid)

        assert_that(response, contains(s.local_xivo_uuid, s.presence))
        self.websocketd_client.get_presence.assert_called_once_with(s.user_uuid)

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
