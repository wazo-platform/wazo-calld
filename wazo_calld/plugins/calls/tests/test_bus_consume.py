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
