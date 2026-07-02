# Copyright 2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock, patch

from hamcrest import assert_that, calling, not_, raises

from ..bus_consume import CallsBusEventHandler
from ..call import Call
from ..exceptions import NoSuchCall
from ..notifier import CallNotifier


class TestCallsBusEventHandler(TestCase):
    def setUp(self):
        ami = Mock()
        ari = Mock()
        collectd = Mock()
        bus_publisher = Mock()
        self.services = Mock()
        xivo_uuid = Mock()
        dial_echo_manager = Mock()
        notifier = Mock()
        self.handler = CallsBusEventHandler(
            ami,
            ari,
            collectd,
            bus_publisher,
            self.services,
            xivo_uuid,
            dial_echo_manager,
            notifier,
        )

    def _make_channel(self, channel_id, name):
        channel = Mock()
        channel.id = channel_id
        channel.json = {'name': name}
        return channel

    def test_relay_channel_entered_bridge_skips_local_channels(self):
        pjsip_channel = self._make_channel('chan-1', 'PJSIP/abc-00000001')
        local_channel = self._make_channel('chan-2', 'Local/s@wazo-record;1')

        bridge = Mock()
        bridge.json = {'channels': ['chan-1', 'chan-2']}
        self.handler.ari.bridges.get.return_value = bridge
        self.handler.ari.channels.get.side_effect = lambda channelId: {
            'chan-1': pjsip_channel,
            'chan-2': local_channel,
        }[channelId]
        self.services.conversation_direction_from_channels.return_value = 'internal'
        self.handler.ari.channels.getChannelVar.return_value = {
            'value': 'internal',
        }

        event = {
            'Uniqueid': 'chan-1',
            'BridgeUniqueid': 'bridge-1',
            'BridgeNumChannels': '2',
        }
        self.handler._relay_channel_entered_bridge(event)

        self.services.make_call_from_channel.assert_called_once_with(
            self.handler.ari, pjsip_channel
        )
        self.handler.notifier.call_updated.assert_called_once()

    def test_relay_channel_left_bridge_skips_local_channels(self):
        pjsip_channel = self._make_channel('chan-1', 'PJSIP/abc-00000001')
        local_channel = self._make_channel('chan-2', 'Local/s@wazo-record;1')

        bridge = Mock()
        bridge.json = {'channels': ['chan-1', 'chan-2']}
        self.handler.ari.bridges.get.return_value = bridge
        self.handler.ari.channels.get.side_effect = lambda channelId: {
            'chan-1': pjsip_channel,
            'chan-2': local_channel,
        }[channelId]
        self.services.conversation_direction_from_channels.return_value = 'internal'
        self.handler.ari.channels.getChannelVar.return_value = {
            'value': 'internal',
        }

        event = {
            'Uniqueid': 'chan-2',
            'BridgeUniqueid': 'bridge-1',
            'BridgeNumChannels': '1',
        }
        self.handler._relay_channel_left_bridge(event)

        self.services.make_call_from_channel.assert_called_once_with(
            self.handler.ari, pjsip_channel
        )
        self.handler.notifier.call_updated.assert_called_once()

    def test_relay_channel_entered_bridge_without_tenant_does_not_raise(self):
        bus = Mock()
        handler = CallsBusEventHandler(
            Mock(),
            Mock(),
            Mock(),
            Mock(),
            self.services,
            Mock(),
            Mock(),
            CallNotifier(bus),
        )
        pjsip_channel = self._make_channel('chan-1', 'PJSIP/mobile-00000001')
        bridge = Mock()
        bridge.json = {'channels': ['chan-1']}
        handler.ari.bridges.get.return_value = bridge
        handler.ari.channels.get.return_value = pjsip_channel
        call = Call('chan-1')  # tenant_uuid is None by default
        self.services.make_call_from_channel.return_value = call
        self.services.conversation_direction_from_channels.return_value = 'unknown'

        event = {
            'Uniqueid': 'chan-1',
            'BridgeUniqueid': 'bridge-1',
            'BridgeNumChannels': '2',
        }
        assert_that(
            calling(handler._relay_channel_entered_bridge).with_args(event),
            not_(raises(Exception)),
        )
        bus.publish.assert_not_called()

    @patch('wazo_calld.plugins.calls.bus_consume.recording')
    def test_attended_transfer_announces_recordings(self, mock_recording):
        event = {
            'Result': 'Success',
            'TransfereeUniqueid': 'chan-transferee',
            'TransferTargetUniqueid': 'chan-target',
        }

        self.handler._attended_transfer(event)

        mock_recording.announce_active_recordings.assert_called_once_with(
            self.handler.ari,
            self.handler.ami,
            ['chan-transferee', 'chan-target'],
        )

    @patch('wazo_calld.plugins.calls.bus_consume.recording')
    def test_attended_transfer_failure_does_not_announce(self, mock_recording):
        event = {'Result': 'Fail'}

        self.handler._attended_transfer(event)

        mock_recording.announce_active_recordings.assert_not_called()

    def test_relay_channel_answered_channel_is_gone(self):
        uniqueid = '123456789.1234'
        event = {
            'ChannelStateDesc': 'Up',
            'Uniqueid': uniqueid,
            'Channel': 'PJSIP/foobar',
        }

        self.services.set_answered_time.side_effect = NoSuchCall(uniqueid)

        assert_that(
            calling(self.handler._relay_channel_answered).with_args(event),
            not_(raises(Exception)),
        )
