# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import sentinel as s

from ari.exceptions import ARINotFound
from hamcrest import assert_that, calling, equal_to, is_, raises

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


class TestChannelSnapshot(TestCase):
    def setUp(self):
        self.ari = Mock()

    def test_get_var_returns_snapshot_value_without_http(self):
        snapshot = {'channelvars': {'WAZO_TENANT_UUID': 'tenant-uuid'}}

        channel = Channel(s.channel_id, self.ari, snapshot=snapshot)
        result = channel.tenant_uuid()

        assert_that(result, equal_to('tenant-uuid'))
        self.ari.channels.getChannelVar.assert_not_called()

    def test_get_var_empty_snapshot_value_behaves_as_not_found_without_http(self):
        snapshot = {'channelvars': {'XIVO_ON_HOLD': ''}}

        channel = Channel(s.channel_id, self.ari, snapshot=snapshot)
        result = channel.on_hold()

        assert_that(result, is_(False))
        self.ari.channels.getChannelVar.assert_not_called()

        assert_that(
            calling(channel._get_var).with_args('XIVO_ON_HOLD'),
            raises(ARINotFound),
        )
        self.ari.channels.getChannelVar.assert_not_called()

    def test_get_var_falls_back_to_live_when_key_absent(self):
        snapshot = {'channelvars': {}}
        self.ari.channels.getChannelVar.return_value = {'value': '1'}

        channel = Channel(s.channel_id, self.ari, snapshot=snapshot)
        result = channel.on_hold()

        assert_that(result, is_(True))
        self.ari.channels.getChannelVar.assert_called_once_with(
            channelId=s.channel_id,
            variable='XIVO_ON_HOLD',
        )

    def test_get_var_without_snapshot_keeps_live_behaviour(self):
        self.ari.channels.getChannelVar.return_value = {'value': '1'}

        channel = Channel(s.channel_id, self.ari)
        result = channel.on_hold()

        assert_that(result, is_(True))
        self.ari.channels.getChannelVar.assert_called_once_with(
            channelId=s.channel_id,
            variable='XIVO_ON_HOLD',
        )

    def test_is_local_and_user_use_snapshot_without_http(self):
        snapshot = {
            'name': 'Local/user-uuid@usersharedlines-0001;1',
            'channelvars': {'WAZO_DEREFERENCED_USERUUID': 'user-uuid'},
        }

        channel = Channel(s.channel_id, self.ari, snapshot=snapshot)

        assert_that(channel.is_local(), is_(True))
        assert_that(channel.user(), equal_to('user-uuid'))
        self.ari.channels.get.assert_not_called()
        self.ari.channels.getChannelVar.assert_not_called()

    def test_dialed_extension_fallback_uses_snapshot_dialplan(self):
        snapshot = {
            'channelvars': {'WAZO_ENTRY_EXTEN': ''},
            'dialplan': {'exten': '1001'},
        }

        channel = Channel(s.channel_id, self.ari, snapshot=snapshot)
        result = channel.dialed_extension()

        assert_that(result, equal_to('1001'))
        self.ari.channels.get.assert_not_called()
        self.ari.channels.getChannelVar.assert_not_called()

    def test_connected_channels_with_prefetched_bridges_makes_no_http(self):
        bridges = [
            Mock(json={'id': 'bridge-1', 'channels': ['channel-1', 'channel-2']})
        ]
        channels_by_id = {
            'channel-2': {
                'name': 'PJSIP/abc-00000001',
                'channelvars': {'WAZO_USERUUID': 'user-2-uuid'},
            }
        }

        channel = Channel('channel-1', self.ari)
        connected = channel.connected_channels(
            bridges=bridges, channels_by_id=channels_by_id
        )

        assert_that(len(connected), equal_to(1))
        connected_channel = connected.pop()
        assert_that(connected_channel.id, equal_to('channel-2'))
        assert_that(connected_channel.user(), equal_to('user-2-uuid'))
        self.ari.bridges.list.assert_not_called()
        self.ari.channels.get.assert_not_called()
        self.ari.channels.getChannelVar.assert_not_called()

    def test_sip_call_id_prefers_cached_wazo_sip_call_id(self):
        snapshot = {
            'channelvars': {
                'CHANNEL(channeltype)': 'PJSIP',
                'WAZO_SIP_CALL_ID': 'the-call-id',
            }
        }

        channel = Channel(s.channel_id, self.ari, snapshot=snapshot)
        result = channel.sip_call_id()

        assert_that(result, equal_to('the-call-id'))
        self.ari.channels.getChannelVar.assert_not_called()

    def test_sip_call_id_falls_back_to_live_pjsip_when_cache_empty(self):
        snapshot = {
            'channelvars': {
                'CHANNEL(channeltype)': 'PJSIP',
                'WAZO_SIP_CALL_ID': '',
            }
        }
        self.ari.channels.getChannelVar.return_value = {'value': 'live-call-id'}

        channel = Channel(s.channel_id, self.ari, snapshot=snapshot)
        result = channel.sip_call_id()

        assert_that(result, equal_to('live-call-id'))
        self.ari.channels.getChannelVar.assert_called_once_with(
            channelId=s.channel_id,
            variable='CHANNEL(pjsip,call-id)',
        )
