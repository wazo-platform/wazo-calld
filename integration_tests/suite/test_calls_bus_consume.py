# Copyright 2016-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
import uuid

from hamcrest import (
    assert_that,
    has_entries,
    has_item,
    is_,
)
from wazo_test_helpers import until

from .helpers.base import IntegrationTest
from .helpers.ari_ import MockChannel
from .helpers.calld import new_call_id
from .helpers.constants import XIVO_UUID, VALID_TENANT
from .helpers.hamcrest_ import a_timestamp
from .helpers.wait_strategy import CalldEverythingOkWaitStrategy


class TestBusConsume(IntegrationTest):

    asset = 'basic_rest'
    wait_strategy = CalldEverythingOkWaitStrategy()

    def setUp(self):
        super().setUp()
        self.amid.reset()
        self.ari.reset()
        self.confd.reset()

    def test_when_channel_created_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id, connected_line_number='', channelvars={'CHANNEL(videonativeformat)': '(vp8)'}))
        self.ari.set_channel_variable({
            call_id: {
                'WAZO_ENTRY_EXTEN': '*10',
                'WAZO_TENANT_UUID': VALID_TENANT,
                'CHANNEL(channeltype)': 'PJSIP',
                'CHANNEL(pjsip,call-id)': 'a-sip-call-id',
            },
        })
        events = self.bus.accumulator(routing_key='calls.call.created')

        self.bus.send_ami_newchannel_event(call_id)

        def assert_function():
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries({
                            'name': 'call_created',
                            'origin_uuid': XIVO_UUID,
                            'data': has_entries({
                                'call_id': call_id,
                                'dialed_extension': '*10',
                                'peer_caller_id_number': '*10',
                                'sip_call_id': 'a-sip-call-id',
                                'is_video': True,
                            })
                        }),
                        headers=has_entries(
                            name='call_created',
                            tenant_uuid=VALID_TENANT,
                        )
                    )
                )
            )

        until.assert_(assert_function, tries=5)

    def test_when_channel_updated_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(
            MockChannel(
                id=call_id,
                state='Up',
                channelvars={
                    'CHANNEL(videonativeformat)': '(vp8)',
                    'WAZO_ANSWER_TIME': '2022-03-08T03:49:00+00:00',
                    'WAZO_TENANT_UUID': VALID_TENANT,
                },
            )
        )
        events = self.bus.accumulator(routing_key='calls.call.updated')

        self.bus.send_ami_newstate_event(call_id)

        def assert_function():
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries({
                            'name': 'call_updated',
                            'origin_uuid': XIVO_UUID,
                            'data': has_entries({
                                'call_id': call_id,
                                'status': 'Up',
                                'hangup_time': None,
                                'answer_time': is_(a_timestamp()),
                                'is_video': True
                            })
                        }),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        )
                    )
                )
            )

        until.assert_(assert_function, tries=5)

    def test_when_channel_answered_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(
            MockChannel(
                id=call_id,
                state='Up',
                channelvars={
                    'WAZO_ANSWER_TIME': '2022-03-08T03:48:00+00:00',
                    'WAZO_TENANT_UUID': VALID_TENANT,
                }
            )
        )
        events = self.bus.accumulator(routing_key='calls.call.answered')

        self.bus.send_ami_newstate_event(call_id, state='Up')

        def assert_function():
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries({
                            'name': 'call_answered',
                            'origin_uuid': XIVO_UUID,
                            'data': has_entries({
                                'call_id': call_id,
                                'status': 'Up',
                                'hangup_time': None,
                                'answer_time': is_(a_timestamp()),
                            })
                        }),
                        headers=has_entries(
                            name='call_answered',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                )
            )

        until.assert_(assert_function, tries=5)

    def test_when_channel_held_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.ari.set_channel_variable({
            call_id: {
                'XIVO_ON_HOLD': '1',
                'WAZO_TENANT_UUID': VALID_TENANT,
            },
        })
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
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries({
                            'name': 'call_held',
                            'origin_uuid': XIVO_UUID,
                            'data': has_entries({'call_id': call_id})
                        }),
                        headers=has_entries(
                            name='call_held',
                            tenant_uuid=VALID_TENANT,
                        )
                    )
                )
            )

        until.assert_(assert_function, tries=5)

    def test_when_channel_resumed_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.ari.set_channel_variable({
            call_id: {
                'XIVO_ON_HOLD': '',
                'WAZO_TENANT_UUID': VALID_TENANT,
            }
        })
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
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries({
                            'name': 'call_resumed',
                            'origin_uuid': XIVO_UUID,
                            'data': has_entries({'call_id': call_id})
                        }),
                        headers=has_entries(
                            name='call_resumed',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                )
            )

        until.assert_(assert_function, tries=5)

    def test_when_channel_dtmf_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.ari.set_channel_variable({
            call_id: {
                'WAZO_TENANT_UUID': VALID_TENANT,
            },
        })
        events = self.bus.accumulator(routing_key='calls.dtmf.created')

        self.bus.send_ami_dtmf_end_digit(call_id, '1')

        def assert_function():
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries({
                            'name': 'call_dtmf_created',
                            'origin_uuid': XIVO_UUID,
                            'data': has_entries({'call_id': call_id, 'digit': '1'})
                        }),
                        headers=has_entries(
                            name='call_dtmf_created',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                )
            )

        until.assert_(assert_function, tries=5)

    def test_missed_call_event(self):
        user_uuid = str(uuid.uuid4())
        conversation_id = '16666244.24'
        events = self.bus.accumulator(routing_key='calls.missed')

        self.bus.send_user_missed_call_userevent(
            user_uuid,
            reason='channel-unavailable',
            hangup_cause='3',
            conversation_id=conversation_id,
        )

        def assert_function():
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries({
                            'name': 'user_missed_call',
                            'origin_uuid': XIVO_UUID,
                            'data': has_entries({
                                'user_uuid': user_uuid,
                                'reason': 'phone-unreachable',
                                'conversation_id': conversation_id,
                            })
                        }),
                        headers=has_entries(
                            name='user_missed_call',
                            tenant_uuid=VALID_TENANT,
                        )
                    )
                )
            )

        until.assert_(assert_function, tries=5)

    def test_when_dnd_enable_event_then_pause_queue_member(self):
        self.bus.send_user_dnd_update('123', True)

        def assert_amid_request():
            assert_that(
                self.amid.requests()['requests'],
                has_item(
                    has_entries(
                        {
                            'method': 'POST',
                            'path': '/1.0/action/QueuePause',
                            'json': has_entries(
                                {
                                    'Interface': 'Local/123@usersharedlines',
                                    'Paused': True,
                                }
                            ),
                        }
                    ),
                ),
            )

        until.assert_(assert_amid_request, tries=5)

    def test_when_dnd_disable_event_then_unpause_queue_member(self):
        self.bus.send_user_dnd_update('123', False)

        def assert_amid_request():
            assert_that(
                self.amid.requests()['requests'],
                has_item(
                    has_entries(
                        {
                            'method': 'POST',
                            'path': '/1.0/action/QueuePause',
                            'json': has_entries(
                                {
                                    'Interface': 'Local/123@usersharedlines',
                                    'Paused': False,
                                }
                            ),
                        }
                    ),
                ),
            )

        until.assert_(assert_amid_request, tries=5)
