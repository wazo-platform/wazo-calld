# Copyright 2016-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_item
from xivo_test_helpers import until

from .helpers.base import IntegrationTest
from .helpers.ari_ import MockChannel
from .helpers.calld import new_call_id
from .helpers.constants import SOME_LINE_ID, XIVO_UUID
from .helpers.wait_strategy import CalldEverythingOkWaitStrategy


class TestBusConsume(IntegrationTest):

    asset = 'basic_rest'
    wait_strategy = CalldEverythingOkWaitStrategy()

    def setUp(self):
        super().setUp()
        self.amid.reset()
        self.ari.reset()
        self.confd.reset()

    def test_when_channel_ended_then_bus_event(self):
        call_id = new_call_id()
        events = self.bus.accumulator(routing_key='calls.call.ended')

        self.bus.send_ami_hangup_event(call_id, base_exten='*10')

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries({
                'name': 'call_ended',
                'origin_uuid': XIVO_UUID,
                'data': has_entries({
                    'call_id': call_id,
                    'dialed_extension': '*10',
                    'sip_call_id': None,
                })
            })))

        until.assert_(assert_function, tries=5)

    def test_when_channel_ended_with_sip_call_id_then_bus_event(self):
        call_id = new_call_id()
        sip_call_id = 'foobar'
        events = self.bus.accumulator(routing_key='calls.call.ended')

        self.bus.send_ami_hangup_event(call_id, base_exten='*10', sip_call_id=sip_call_id)

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries({
                'name': 'call_ended',
                'origin_uuid': XIVO_UUID,
                'data': has_entries({
                    'call_id': call_id,
                    'dialed_extension': '*10',
                    'sip_call_id': sip_call_id,
                })
            })))

        until.assert_(assert_function, tries=5)

    def test_when_channel_ended_with_line_id_then_bus_event(self):
        call_id = new_call_id()
        events = self.bus.accumulator(routing_key='calls.call.ended')

        line_id = SOME_LINE_ID
        self.bus.send_ami_hangup_event(call_id, base_exten='*10', line_id=line_id)

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries({
                'name': 'call_ended',
                'origin_uuid': XIVO_UUID,
                'data': has_entries({
                    'call_id': call_id,
                    'dialed_extension': '*10',
                    'line_id': SOME_LINE_ID,
                })
            })))

        until.assert_(assert_function, tries=5)

    def test_when_channel_created_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id, connected_line_number=''))
        self.ari.set_channel_variable({
            call_id: {
                'XIVO_BASE_EXTEN': '*10',
                'CHANNEL(channeltype)': 'PJSIP',
                'CHANNEL(pjsip,call-id)': 'a-sip-call-id',
            },
        })
        events = self.bus.accumulator(routing_key='calls.call.created')

        self.bus.send_ami_newchannel_event(call_id)

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries({
                'name': 'call_created',
                'origin_uuid': XIVO_UUID,
                'data': has_entries({
                    'call_id': call_id,
                    'dialed_extension': '*10',
                    'peer_caller_id_number': '*10',
                    'sip_call_id': 'a-sip-call-id',
                })
            })))

        until.assert_(assert_function, tries=5)

    def test_when_channel_updated_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id, state='Up'))
        events = self.bus.accumulator(routing_key='calls.call.updated')

        self.bus.send_ami_newstate_event(call_id)

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries({
                'name': 'call_updated',
                'origin_uuid': XIVO_UUID,
                'data': has_entries({'call_id': call_id, 'status': 'Up'})
            })))

        until.assert_(assert_function, tries=5)

    def test_when_channel_answered_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id, state='Up'))
        events = self.bus.accumulator(routing_key='calls.call.answered')

        self.bus.send_ami_newstate_event(call_id, state='Up')

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries({
                'name': 'call_answered',
                'origin_uuid': XIVO_UUID,
                'data': has_entries({'call_id': call_id, 'status': 'Up'})
            })))

        until.assert_(assert_function, tries=5)

    def test_when_channel_held_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.ari.set_channel_variable({call_id: {'XIVO_ON_HOLD': '1'}})
        events = self.bus.accumulator(routing_key='calls.hold.created')

        self.bus.send_ami_hold_event(call_id)

        def assert_function():
            assert_that(self.amid.requests()['requests'], has_item(has_entries({
                'method': 'POST',
                'path': '/1.0/action/Setvar',
                'json': has_entries({
                    'Channel': call_id,
                    'Variable': 'XIVO_ON_HOLD',
                    'Value': '1'
                }),
            })))
            assert_that(events.accumulate(), has_item(has_entries({
                'name': 'call_held',
                'origin_uuid': XIVO_UUID,
                'data': has_entries({'call_id': call_id})
            })))

        until.assert_(assert_function, tries=5)

    def test_when_channel_resumed_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.ari.set_channel_variable({call_id: {'XIVO_ON_HOLD': ''}})
        events = self.bus.accumulator(routing_key='calls.hold.deleted')

        self.bus.send_ami_unhold_event(call_id)

        def assert_function():
            assert_that(self.amid.requests()['requests'], has_item(has_entries({
                'method': 'POST',
                'path': '/1.0/action/Setvar',
                'json': has_entries({
                    'Channel': call_id,
                    'Variable': 'XIVO_ON_HOLD',
                    'Value': ''
                }),
            })))
            assert_that(events.accumulate(), has_item(has_entries({
                'name': 'call_resumed',
                'origin_uuid': XIVO_UUID,
                'data': has_entries({'call_id': call_id})
            })))

        until.assert_(assert_function, tries=5)

    def test_when_channel_dtmf_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        events = self.bus.accumulator(routing_key='calls.dtmf.created')

        self.bus.send_ami_dtmf_end_digit(call_id, '1')

        def assert_function():
            assert_that(events.accumulate(), has_item(has_entries({
                'name': 'call_dtmf_created',
                'origin_uuid': XIVO_UUID,
                'data': has_entries({'call_id': call_id, 'digit': '1'})
            })))

        until.assert_(assert_function, tries=5)
