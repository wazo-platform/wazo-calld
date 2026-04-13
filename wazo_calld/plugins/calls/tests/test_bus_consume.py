# Copyright 2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock

from hamcrest import assert_that, calling, not_, raises

from ..bus_consume import CallsBusEventHandler
from ..exceptions import NoSuchCall


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
