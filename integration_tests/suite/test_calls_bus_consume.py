# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import time

from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_entry
from hamcrest import has_item
from xivo_test_helpers import until

from .test_api.base import IntegrationTest
from .test_api.ari import MockChannel
from .test_api.ctid_ng import new_call_id
from .test_api.constants import XIVO_UUID


class TestDialedFrom(IntegrationTest):

    asset = 'basic_rest'

    @classmethod
    def setUpClass(cls):
        super(TestDialedFrom, cls).setUpClass()
        time.sleep(4)  # wait for xivo-ctid-ng to connect to the bus

    def setUp(self):
        super(TestDialedFrom, self).setUp()
        self.ari.reset()
        self.confd.reset()

    def test_when_channel_ended_then_bus_event(self):
        call_id = new_call_id()
        self.bus.listen_events(routing_key='calls.call.ended')

        self.bus.send_ami_hangup_event(call_id)

        def assert_function():
            assert_that(self.bus.events(), has_item(has_entries({
                'name': 'call_ended',
                'origin_uuid': XIVO_UUID,
                'data': has_entry('call_id', call_id)
            })))

        until.assert_(assert_function, tries=5)

    def test_when_channel_created_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.bus.listen_events(routing_key='calls.call.created')

        self.bus.send_ami_newchannel_event(call_id)

        def assert_function():
            assert_that(self.bus.events(), has_item(has_entries({
                'name': 'call_created',
                'origin_uuid': XIVO_UUID,
                'data': has_entry('call_id', call_id)
            })))

        until.assert_(assert_function, tries=5)

    def test_when_channel_updated_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id, state='Up'))
        self.bus.listen_events(routing_key='calls.call.updated')

        self.bus.send_ami_newstate_event(call_id)

        def assert_function():
            assert_that(self.bus.events(), has_item(has_entries({
                'name': 'call_updated',
                'origin_uuid': XIVO_UUID,
                'data': has_entries({'call_id': call_id, 'status': 'Up'})
            })))

        until.assert_(assert_function, tries=5)
