# Copyright 2016-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
import uuid

from hamcrest import all_of, assert_that, has_entries, has_item, is_
from wazo_test_helpers import until

from .helpers.ari_ import MockBridge, MockChannel
from .helpers.base import IntegrationTest
from .helpers.calld import new_call_id
from .helpers.constants import SOME_STASIS_APP, VALID_TENANT, XIVO_UUID
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
        self.ari.set_channels(
            MockChannel(
                id=call_id,
                connected_line_number='',
                channelvars={'CHANNEL(videonativeformat)': '(vp8)'},
            )
        )
        self.ari.set_channel_variable(
            {
                call_id: {
                    'WAZO_ENTRY_EXTEN': '*10',
                    'WAZO_TENANT_UUID': VALID_TENANT,
                    'CHANNEL(channeltype)': 'PJSIP',
                    'CHANNEL(pjsip,call-id)': 'a-sip-call-id',
                    'WAZO_CALL_DIRECTION': 'inbound',
                },
            }
        )
        events = self.bus.accumulator(headers={'name': 'call_created'})

        self.bus.send_ami_newchannel_event(call_id)

        def assert_function():
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'call_created',
                                'origin_uuid': XIVO_UUID,
                                'data': has_entries(
                                    {
                                        'call_id': call_id,
                                        'dialed_extension': '*10',
                                        'peer_caller_id_number': '*10',
                                        'sip_call_id': 'a-sip-call-id',
                                        'is_video': True,
                                        'direction': 'inbound',
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            name='call_created',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
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
                },
            )
        )
        self.ari.set_channel_variable(
            {
                call_id: {
                    'WAZO_TENANT_UUID': VALID_TENANT,
                    'WAZO_CALL_DIRECTION': 'outbound',
                },
            }
        )
        events = self.bus.accumulator(headers={'name': 'call_updated'})

        self.bus.send_ami_newstate_event(call_id)

        def assert_function():
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'call_updated',
                                'origin_uuid': XIVO_UUID,
                                'data': has_entries(
                                    {
                                        'call_id': call_id,
                                        'status': 'Up',
                                        'hangup_time': None,
                                        'answer_time': is_(a_timestamp()),
                                        'is_video': True,
                                        'direction': 'outbound',
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(assert_function, tries=5)

    def test_when_channel_joins_bridge_call_direction_updated(self):
        first_channel_id = new_call_id()
        second_channel_id = new_call_id()
        self.ari.set_channels(
            MockChannel(id=first_channel_id, state='Up'),
            MockChannel(id=second_channel_id, state='Up'),
        )
        self.ari.set_channel_variable(
            {
                first_channel_id: {
                    'WAZO_TENANT_UUID': VALID_TENANT,
                },
                second_channel_id: {
                    'WAZO_TENANT_UUID': VALID_TENANT,
                    'WAZO_CALL_DIRECTION': 'outbound',
                },
            }
        )
        self.ari.set_bridges(
            MockBridge(
                first_channel_id,
                channels=[first_channel_id, second_channel_id],
            )
        )

        events = self.bus.accumulator(headers={'name': 'call_updated'})

        self.bus.send_ami_newchannel_event(second_channel_id)
        self.bus.send_ami_newstate_event(second_channel_id)
        self.bus.send_ami_newstate_event(first_channel_id)

        def assert_function():
            assert_that(
                events.accumulate(with_headers=True),
                all_of(
                    has_item(
                        has_entries(
                            message=has_entries(
                                {
                                    'name': 'call_updated',
                                    'origin_uuid': XIVO_UUID,
                                    'data': has_entries(
                                        {
                                            'call_id': first_channel_id,
                                            'status': 'Up',
                                            'direction': 'outbound',
                                        }
                                    ),
                                }
                            ),
                            headers=has_entries(
                                name='call_updated',
                                tenant_uuid=VALID_TENANT,
                            ),
                        )
                    ),
                    has_item(
                        has_entries(
                            message=has_entries(
                                {
                                    'name': 'call_updated',
                                    'origin_uuid': XIVO_UUID,
                                    'data': has_entries(
                                        {
                                            'call_id': second_channel_id,
                                            'status': 'Up',
                                            'direction': 'outbound',
                                        }
                                    ),
                                }
                            ),
                            headers=has_entries(
                                name='call_updated',
                                tenant_uuid=VALID_TENANT,
                            ),
                        )
                    ),
                ),
            )

        until.assert_(assert_function, tries=5)

    def test_when_channel_leaves_bridge_call_direction_updated(self):
        first_channel_id = new_call_id()
        second_channel_id = new_call_id()
        third_channel_id = new_call_id()
        self.ari.set_bridges(
            MockBridge(
                first_channel_id,
                channels=[first_channel_id, second_channel_id, third_channel_id],
            )
        )
        self.ari.set_channels(
            MockChannel(id=first_channel_id, state='Up'),
            MockChannel(id=second_channel_id, state='Up'),
            MockChannel(id=third_channel_id, state='Up'),
        )
        self.ari.set_channel_variable(
            {
                first_channel_id: {
                    'WAZO_TENANT_UUID': VALID_TENANT,
                },
                second_channel_id: {
                    'WAZO_TENANT_UUID': VALID_TENANT,
                },
                third_channel_id: {
                    'WAZO_TENANT_UUID': VALID_TENANT,
                    'WAZO_CALL_DIRECTION': 'inbound',
                },
            }
        )

        self.ari.set_channels(
            MockChannel(id=first_channel_id, state='Up'),
            MockChannel(id=second_channel_id, state='Up'),
            MockChannel(id=third_channel_id, state='Down'),
        )

        self.ari.set_bridges(
            MockBridge(first_channel_id, channels=[first_channel_id, second_channel_id])
        )

        events_ended = self.bus.accumulator(headers={'name': 'call_ended'})
        self.bus.send_ami_bridge_leave_event(
            channel_id=third_channel_id,
            bridge_id=first_channel_id,
            bridge_num_channels=2,
        )
        self.stasis.event_channel_destroyed(third_channel_id, SOME_STASIS_APP)
        self.bus.send_ami_hangup_event(channel_id=third_channel_id)

        events_updated = self.bus.accumulator(headers={'name': 'call_updated'})
        self.bus.send_ami_newstate_event(second_channel_id)
        self.bus.send_ami_newstate_event(first_channel_id)

        def assert_third_call_ended_is_inbound():
            assert_that(
                events_ended.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'call_ended',
                                'origin_uuid': XIVO_UUID,
                                'data': has_entries(
                                    {
                                        'call_id': third_channel_id,
                                        'direction': 'inbound',
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            name='call_ended',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(assert_third_call_ended_is_inbound, tries=5)

        def assert_first_and_second_calls_are_internal():
            assert_that(
                events_updated.accumulate(with_headers=True),
                all_of(
                    has_item(
                        has_entries(
                            message=has_entries(
                                {
                                    'name': 'call_updated',
                                    'origin_uuid': XIVO_UUID,
                                    'data': has_entries(
                                        {
                                            'call_id': first_channel_id,
                                            'status': 'Up',
                                            'direction': 'internal',
                                        }
                                    ),
                                }
                            ),
                            headers=has_entries(
                                name='call_updated',
                                tenant_uuid=VALID_TENANT,
                            ),
                        )
                    ),
                    has_item(
                        has_entries(
                            message=has_entries(
                                {
                                    'name': 'call_updated',
                                    'origin_uuid': XIVO_UUID,
                                    'data': has_entries(
                                        {
                                            'call_id': second_channel_id,
                                            'status': 'Up',
                                            'direction': 'internal',
                                        }
                                    ),
                                }
                            ),
                            headers=has_entries(
                                name='call_updated',
                                tenant_uuid=VALID_TENANT,
                            ),
                        )
                    ),
                ),
            )

        until.assert_(assert_first_and_second_calls_are_internal, tries=5)

    def test_when_channel_answered_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(
            MockChannel(
                id=call_id,
                state='Up',
                channelvars={
                    'WAZO_ANSWER_TIME': '2022-03-08T03:48:00+00:00',
                },
            )
        )
        self.ari.set_channel_variable(
            {
                call_id: {
                    'WAZO_TENANT_UUID': VALID_TENANT,
                    'WAZO_CALL_DIRECTION': 'internal',
                },
            }
        )
        events = self.bus.accumulator(headers={'name': 'call_answered'})

        self.bus.send_ami_newstate_event(call_id, state='Up')

        def assert_function():
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'call_answered',
                                'origin_uuid': XIVO_UUID,
                                'data': has_entries(
                                    {
                                        'call_id': call_id,
                                        'status': 'Up',
                                        'hangup_time': None,
                                        'answer_time': is_(a_timestamp()),
                                        'direction': 'internal',
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            name='call_answered',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(assert_function, tries=5)

    def test_when_channel_held_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.ari.set_channel_variable(
            {
                call_id: {
                    'XIVO_ON_HOLD': '1',
                    'WAZO_TENANT_UUID': VALID_TENANT,
                },
            }
        )
        events = self.bus.accumulator(headers={'name': 'call_held'})

        self.bus.send_ami_hold_event(call_id)

        def assert_function():
            assert_that(
                self.amid.requests()['requests'],
                has_item(
                    has_entries(
                        {
                            'method': 'POST',
                            'path': '/1.0/action/Setvar',
                            'json': has_entries(
                                {
                                    'Channel': call_id,
                                    'Variable': 'XIVO_ON_HOLD',
                                    'Value': '1',
                                }
                            ),
                        }
                    )
                ),
            )
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'call_held',
                                'origin_uuid': XIVO_UUID,
                                'data': has_entries({'call_id': call_id}),
                            }
                        ),
                        headers=has_entries(
                            name='call_held',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(assert_function, tries=5)

    def test_when_channel_resumed_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.ari.set_channel_variable(
            {
                call_id: {
                    'XIVO_ON_HOLD': '',
                    'WAZO_TENANT_UUID': VALID_TENANT,
                }
            }
        )
        events = self.bus.accumulator(headers={'name': 'call_resumed'})

        self.bus.send_ami_unhold_event(call_id)

        def assert_function():
            assert_that(
                self.amid.requests()['requests'],
                has_item(
                    has_entries(
                        {
                            'method': 'POST',
                            'path': '/1.0/action/Setvar',
                            'json': has_entries(
                                {
                                    'Channel': call_id,
                                    'Variable': 'XIVO_ON_HOLD',
                                    'Value': '',
                                }
                            ),
                        }
                    )
                ),
            )
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'call_resumed',
                                'origin_uuid': XIVO_UUID,
                                'data': has_entries({'call_id': call_id}),
                            }
                        ),
                        headers=has_entries(
                            name='call_resumed',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(assert_function, tries=5)

    def test_when_channel_dtmf_then_bus_event(self):
        call_id = new_call_id()
        self.ari.set_channels(MockChannel(id=call_id))
        self.ari.set_channel_variable(
            {
                call_id: {
                    'WAZO_TENANT_UUID': VALID_TENANT,
                },
            }
        )
        events = self.bus.accumulator(headers={'name': 'call_dtmf_created'})

        self.bus.send_ami_dtmf_end_digit(call_id, '1')

        def assert_function():
            assert_that(
                events.accumulate(with_headers=True),
                has_item(
                    has_entries(
                        message=has_entries(
                            {
                                'name': 'call_dtmf_created',
                                'origin_uuid': XIVO_UUID,
                                'data': has_entries({'call_id': call_id, 'digit': '1'}),
                            }
                        ),
                        headers=has_entries(
                            name='call_dtmf_created',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(assert_function, tries=5)

    def test_missed_call_event(self):
        user_uuid = str(uuid.uuid4())
        conversation_id = '16666244.24'
        events = self.bus.accumulator(headers={'name': 'user_missed_call'})

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
                        message=has_entries(
                            {
                                'name': 'user_missed_call',
                                'origin_uuid': XIVO_UUID,
                                'data': has_entries(
                                    {
                                        'user_uuid': user_uuid,
                                        'reason': 'phone-unreachable',
                                        'conversation_id': conversation_id,
                                    }
                                ),
                            }
                        ),
                        headers=has_entries(
                            name='user_missed_call',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
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
