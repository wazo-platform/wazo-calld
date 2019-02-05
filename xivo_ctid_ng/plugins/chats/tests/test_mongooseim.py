# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from requests import HTTPError
from hamcrest import (
    assert_that,
    calling,
    equal_to,
    raises,
)
from mock import Mock, patch

from ..mongooseim import Client


class TestChatsService(unittest.TestCase):

    def setUp(self):
        self.host = 'localhost',
        self.port = 8088
        self.client = Client(self.host, self.port)
        self.from_jid = 'alice@localhost'
        self.to_jid = 'bob@localhost'

    @patch('xivo_ctid_ng.plugins.chats.mongooseim.requests')
    def test_get_user_history_error(self, requests):
        requests.get.return_value = Mock(status_code=500,
                                         raise_for_status=Mock(side_effect=HTTPError()))

        assert_that(calling(self.client.get_user_history).with_args(self.from_jid),
                    raises(HTTPError))

    def test_url(self):
        url = self.client.url(self.from_jid)
        assert_that(url, equal_to('http://{}:{}/api/alice%40localhost'.format(self.host, self.port)))

    @patch('xivo_ctid_ng.plugins.chats.mongooseim.requests')
    def test_send_message_symbols(self, requests):
        msg = 'Ampersand&Buggy'
        self.client.send_message(self.from_jid, self.to_jid, msg)
        expected_url = 'http://{}:{}/api/messages'.format(self.host, self.port)
        expected_json = {'caller': self.from_jid,
                         'to': self.to_jid,
                         'body': 'Ampersand#26Buggy'}
        requests.post.assert_called_once_with(expected_url, json=expected_json)
