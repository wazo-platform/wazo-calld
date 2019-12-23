# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from mock import (
    Mock,
    sentinel as s,
)
from hamcrest import (
    assert_that,
    equal_to,
)

from ari.exceptions import ARINotFound

from ..ari_ import Channel


class TestChannelHelper(TestCase):

    def setUp(self):
        self.ari = Mock()

    def test_dialed_extension_when_no_channel_exist(self):
        self.ari.channels.get.side_effect = ARINotFound(
            original_error='no channel',
            ari_client=self.ari,
        )

        channel = Channel(s.channel_id, self.ari)
        result = channel.dialed_extension()

        assert_that(result, equal_to(None))

    def test_dialed_extension_going_through_the_wazo_dialplan(self):
        self.ari.channels.get.return_value = mocked_channel = Mock()
        mocked_channel.getChannelVar.return_value = {'value': s.exten}

        channel = Channel(s.channel_id, self.ari)
        result = channel.dialed_extension()

        assert_that(result, equal_to(s.exten))

    def test_dialed_extension_when_dialing_right_into_stasis(self):
        self.ari.channels.get.return_value = mocked_channel = Mock()
        mocked_channel.getChannelVar.side_effect = ARINotFound(
            original_error='no var',
            ari_client=self.ari,
        )
        mocked_channel.json = {'dialplan': {'exten': s.exten}}

        channel = Channel(s.channel_id, self.ari)
        result = channel.dialed_extension()

        assert_that(result, equal_to(s.exten))
