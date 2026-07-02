# Copyright 2019-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import sentinel as s

from ari.exceptions import ARINotFound
from hamcrest import assert_that, contains_inanyorder, equal_to, is_

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


class TestChannelSnapshot(TestCase):
    def setUp(self):
        self.ari = Mock()

    def test_variable_in_snapshot_is_returned_without_http_request(self):
        snapshot = {'channelvars': {'WAZO_TENANT_UUID': 'my-tenant'}}

        channel = Channel(s.channel_id, self.ari, snapshot=snapshot)
        result = channel.tenant_uuid()

        assert_that(result, equal_to('my-tenant'))
        self.ari.channels.getChannelVar.assert_not_called()

    def test_empty_variable_in_snapshot_behaves_as_unset_without_http_request(self):
        snapshot = {'channelvars': {'XIVO_ON_HOLD': ''}}

        channel = Channel(s.channel_id, self.ari, snapshot=snapshot)
        result = channel.on_hold()

        assert_that(result, is_(False))
        self.ari.channels.getChannelVar.assert_not_called()

    def test_variable_absent_from_snapshot_falls_back_to_live_request(self):
        snapshot = {'channelvars': {'SOME_OTHER_VAR': 'value'}}
        self.ari.channels.getChannelVar.return_value = {'value': 'my-tenant'}

        channel = Channel(s.channel_id, self.ari, snapshot=snapshot)
        result = channel.tenant_uuid()

        assert_that(result, equal_to('my-tenant'))
        self.ari.channels.getChannelVar.assert_called_once_with(
            channelId=s.channel_id,
            variable='WAZO_TENANT_UUID',
        )

    def test_no_snapshot_keeps_live_behavior(self):
        self.ari.channels.getChannelVar.return_value = {'value': 'my-tenant'}

        channel = Channel(s.channel_id, self.ari)
        result = channel.tenant_uuid()

        assert_that(result, equal_to('my-tenant'))
        self.ari.channels.getChannelVar.assert_called_once_with(
            channelId=s.channel_id,
            variable='WAZO_TENANT_UUID',
        )

    def test_is_local_from_snapshot_name_without_http_request(self):
        channel = Channel(
            s.channel_id, self.ari, snapshot={'name': 'Local/foo@bar-00000001;2'}
        )
        assert_that(channel.is_local(), is_(True))

        channel = Channel(
            s.channel_id, self.ari, snapshot={'name': 'PJSIP/foo-00000001'}
        )
        assert_that(channel.is_local(), is_(False))

        self.ari.channels.get.assert_not_called()

    def test_dialed_extension_fallback_from_snapshot_dialplan(self):
        snapshot = {
            'channelvars': {'WAZO_ENTRY_EXTEN': ''},
            'dialplan': {'exten': '1001'},
        }

        channel = Channel(s.channel_id, self.ari, snapshot=snapshot)
        result = channel.dialed_extension()

        assert_that(result, equal_to('1001'))
        self.ari.channels.getChannelVar.assert_not_called()
        self.ari.channels.get.assert_not_called()

    def test_connected_channels_with_prefetched_bridges_and_snapshots(self):
        bridge = Mock()
        bridge.json = {'channels': ['channel-id', 'other-channel-id']}
        other_snapshot = {
            'name': 'PJSIP/other-00000002',
            'channelvars': {'WAZO_USERUUID': 'other-user-uuid'},
        }
        channels_by_id = {'other-channel-id': other_snapshot}

        channel = Channel('channel-id', self.ari, snapshot={'name': 'PJSIP/x-1'})
        result = channel.connected_channels(
            bridges=[bridge], channels_by_id=channels_by_id
        )

        assert_that(
            [connected.id for connected in result],
            contains_inanyorder('other-channel-id'),
        )
        assert_that(
            [connected.user() for connected in result],
            contains_inanyorder('other-user-uuid'),
        )
        self.ari.bridges.list.assert_not_called()
        self.ari.channels.getChannelVar.assert_not_called()

    def test_sip_call_id_prefers_snapshot_wazo_sip_call_id(self):
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

    def test_sip_call_id_falls_back_to_live_pjsip_read_when_empty(self):
        snapshot = {
            'channelvars': {
                'CHANNEL(channeltype)': 'PJSIP',
                'WAZO_SIP_CALL_ID': '',
            }
        }
        self.ari.channels.getChannelVar.return_value = {'value': 'the-call-id'}

        channel = Channel(s.channel_id, self.ari, snapshot=snapshot)
        result = channel.sip_call_id()

        assert_that(result, equal_to('the-call-id'))
        self.ari.channels.getChannelVar.assert_called_once_with(
            channelId=s.channel_id,
            variable='CHANNEL(pjsip,call-id)',
        )
