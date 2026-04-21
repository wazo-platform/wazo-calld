# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import sentinel as s

from ari.exceptions import ARINotFound
from hamcrest import assert_that, equal_to, is_

from ..ari_ import Channel


class TestChannelHelper(TestCase):
    def setUp(self):
        self.ari = Mock()

    def test_dialed_extension_when_no_channel_exist(self):
        self.ari.channels.getChannelVar.side_effect = ARINotFound(
            original_error='no channel',
            ari_client=self.ari,
        )
        self.ari.channels.get.side_effect = ARINotFound(
            original_error='no channel',
            ari_client=self.ari,
        )

        channel = Channel(s.channel_id, self.ari)
        result = channel.dialed_extension()

        assert_that(result, equal_to(None))

    def test_dialed_extension_going_through_the_wazo_dialplan(self):
        self.ari.channels.getChannelVar.return_value = {'value': s.exten}
        mocked_channel = self.ari.channels.get.return_value = Mock()
        mocked_channel.json = {'dialplan': {'exten': 's'}}

        channel = Channel(s.channel_id, self.ari)
        result = channel.dialed_extension()

        assert_that(result, equal_to(s.exten))

    def test_dialed_extension_when_dialing_right_into_stasis(self):
        self.ari.channels.getChannelVar.side_effect = ARINotFound(
            original_error='no var',
            ari_client=self.ari,
        )
        self.ari.channels.get.return_value = mocked_channel = Mock()
        mocked_channel.json = {'dialplan': {'exten': s.exten}}

        channel = Channel(s.channel_id, self.ari)
        result = channel.dialed_extension()

        assert_that(result, equal_to(s.exten))

    def test_is_group_auto_recorded_returns_true_when_shared_var_is_1(self):
        self.ari.channels.getChannelVar.return_value = {'value': '1'}

        channel = Channel(s.channel_id, self.ari)
        result = channel.is_group_auto_recorded()

        assert_that(result, is_(True))
        self.ari.channels.getChannelVar.assert_called_once_with(
            channelId=s.channel_id,
            variable='SHARED(WAZO_RECORD_GROUP_CALLEE)',
        )

    def test_is_group_auto_recorded_returns_false_when_not_set(self):
        self.ari.channels.getChannelVar.side_effect = ARINotFound(
            original_error='no var',
            ari_client=self.ari,
        )

        channel = Channel(s.channel_id, self.ari)
        result = channel.is_group_auto_recorded()

        assert_that(result, is_(False))

    def test_is_queue_auto_recorded_returns_true_when_shared_var_is_1(self):
        self.ari.channels.getChannelVar.return_value = {'value': '1'}

        channel = Channel(s.channel_id, self.ari)
        result = channel.is_queue_auto_recorded()

        assert_that(result, is_(True))
        self.ari.channels.getChannelVar.assert_called_once_with(
            channelId=s.channel_id,
            variable='SHARED(WAZO_RECORD_QUEUE_CALLEE)',
        )

    def test_is_queue_auto_recorded_returns_false_when_not_set(self):
        self.ari.channels.getChannelVar.side_effect = ARINotFound(
            original_error='no var',
            ari_client=self.ari,
        )

        channel = Channel(s.channel_id, self.ari)
        result = channel.is_queue_auto_recorded()

        assert_that(result, is_(False))
