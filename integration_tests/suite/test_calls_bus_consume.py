# Copyright 2016-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import uuid

from hamcrest import (
    all_of,
    assert_that,
    contains_exactly,
    has_entries,
    has_item,
    has_length,
    is_,
    not_,
)
from wazo_test_helpers import until
from wazo_test_helpers.hamcrest.timestamp import an_iso_timestamp

from .helpers.ari_ import MockBridge, MockChannel
from .helpers.base import IntegrationTest
from .helpers.calld import new_call_id
from .helpers.confd import MockUser
from .helpers.constants import SOME_STASIS_APP, VALID_TENANT, XIVO_UUID
from .helpers.wait_strategy import CalldEverythingOkWaitStrategy


def group_member_interface(user_uuid):
    return f'Local/{user_uuid}@usersharedlines'


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
                                        'answer_time': is_(an_iso_timestamp()),
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
                                        'answer_time': is_(an_iso_timestamp()),
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

    def _group_member(self, user_uuid, paused, queue='group1'):
        return {
            'Queue': queue,
            'Location': group_member_interface(user_uuid),
            'Paused': '1' if paused else '0',
        }

    def _queue_status_requests(self):
        return [
            request
            for request in self.amid.requests()['requests']
            if request['path'] == '/1.0/action/QueueStatus'
        ]

    def _wait_for_dnd_synchronization(self, count=1):
        def queue_status_requested():
            assert_that(self._queue_status_requests(), has_length(count))

        until.assert_(queue_status_requested, timeout=15, interval=0.5)

    def _assert_queue_pause(self, user_uuid, paused):
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
                                    'Interface': group_member_interface(user_uuid),
                                    'Paused': paused,
                                }
                            ),
                        }
                    ),
                ),
            )

        until.assert_(assert_amid_request, tries=10)

    def _queue_pause_interfaces(self):
        return [
            request['json']['Interface']
            for request in self.amid.requests()['requests']
            if request['path'] == '/1.0/action/QueuePause'
        ]

    def _wait_for_corrections(self, sentinel_uuid):
        '''Wait until the member reported last by QueueStatus is corrected.

        The synchronization corrects members in the order QueueStatus
        reported them, so once the last one is done no other correction is
        coming and the absence of a request can be asserted.

        '''
        self._assert_queue_pause(sentinel_uuid, paused=True)

    def _assert_no_queue_pause(self, user_uuid):
        assert_that(
            self.amid.requests()['requests'],
            not_(
                has_item(
                    has_entries(
                        {
                            'path': '/1.0/action/QueuePause',
                            'json': has_entries(
                                {'Interface': group_member_interface(user_uuid)}
                            ),
                        }
                    )
                )
            ),
        )

    def test_when_dnd_enable_event_then_pause_queue_member(self):
        self.bus.send_user_dnd_update('123', True)

        self._assert_queue_pause('123', paused=True)

    def test_when_dnd_disable_event_then_unpause_queue_member(self):
        self.bus.send_user_dnd_update('123', False)

        self._assert_queue_pause('123', paused=False)

    def test_when_asterisk_restarts_then_dnd_member_is_paused_again(self):
        user_uuid = str(uuid.uuid4())
        self.confd.set_users(MockUser(uuid=user_uuid, dnd_enabled=True))
        self.amid.set_queue_status(self._group_member(user_uuid, paused=False))

        self.bus.send_ami_fully_booted_event()

        self._assert_queue_pause(user_uuid, paused=True)

    def test_when_asterisk_restarts_then_stale_pause_is_removed(self):
        user_uuid = str(uuid.uuid4())
        self.confd.set_users(MockUser(uuid=user_uuid, dnd_enabled=False))
        self.amid.set_queue_status(self._group_member(user_uuid, paused=True))

        self.bus.send_ami_fully_booted_event()

        self._assert_queue_pause(user_uuid, paused=False)

    def test_when_asterisk_restarts_then_members_in_sync_are_left_alone(self):
        paused_uuid = str(uuid.uuid4())
        unpaused_uuid = str(uuid.uuid4())
        sentinel_uuid = str(uuid.uuid4())
        self.confd.set_users(
            MockUser(uuid=paused_uuid, dnd_enabled=True),
            MockUser(uuid=unpaused_uuid, dnd_enabled=False),
            MockUser(uuid=sentinel_uuid, dnd_enabled=True),
        )
        self.amid.set_queue_status(
            self._group_member(paused_uuid, paused=True),
            self._group_member(unpaused_uuid, paused=False),
            self._group_member(sentinel_uuid, paused=False),
        )

        self.bus.send_ami_fully_booted_event()
        self._wait_for_corrections(sentinel_uuid)

        self._assert_no_queue_pause(paused_uuid)
        self._assert_no_queue_pause(unpaused_uuid)

    def test_when_asterisk_restarts_then_member_unknown_to_confd_is_unpaused(self):
        user_uuid = str(uuid.uuid4())
        self.confd.set_users()
        self.amid.set_queue_status(self._group_member(user_uuid, paused=True))

        self.bus.send_ami_fully_booted_event()

        self._assert_queue_pause(user_uuid, paused=False)

    def test_when_asterisk_restarts_then_non_group_members_are_ignored(self):
        sentinel_uuid = str(uuid.uuid4())
        self.confd.set_users(MockUser(uuid=sentinel_uuid, dnd_enabled=True))
        self.amid.set_queue_status(
            {'Queue': 'queue1', 'Location': 'Agent/1001', 'Paused': '1'},
            {'Queue': 'queue1', 'Location': 'PJSIP/abcdef', 'Paused': '1'},
            {'Queue': 'queue1', 'Location': 'Local/1002@agentcallback', 'Paused': '1'},
            self._group_member(sentinel_uuid, paused=False),
        )

        self.bus.send_ami_fully_booted_event()
        self._wait_for_corrections(sentinel_uuid)

        assert_that(
            self._queue_pause_interfaces(),
            contains_exactly(group_member_interface(sentinel_uuid)),
        )

    def test_when_asterisk_restarts_then_member_of_several_groups_is_paused_once(self):
        user_uuid = str(uuid.uuid4())
        self.confd.set_users(MockUser(uuid=user_uuid, dnd_enabled=True))
        self.amid.set_queue_status(
            self._group_member(user_uuid, paused=False, queue='group1'),
            self._group_member(user_uuid, paused=False, queue='group2'),
            self._group_member(user_uuid, paused=False, queue='group3'),
        )

        self.bus.send_ami_fully_booted_event()
        self._assert_queue_pause(user_uuid, paused=True)

        pause_requests = [
            request
            for request in self.amid.requests()['requests']
            if request['path'] == '/1.0/action/QueuePause'
        ]
        assert_that(pause_requests, has_length(1))

    def test_when_asterisk_restarts_then_partially_paused_member_is_paused(self):
        user_uuid = str(uuid.uuid4())
        self.confd.set_users(MockUser(uuid=user_uuid, dnd_enabled=True))
        self.amid.set_queue_status(
            self._group_member(user_uuid, paused=True, queue='group1'),
            self._group_member(user_uuid, paused=False, queue='group2'),
        )

        self.bus.send_ami_fully_booted_event()

        self._assert_queue_pause(user_uuid, paused=True)

    def test_when_asterisk_restarts_then_partially_paused_member_is_unpaused(self):
        user_uuid = str(uuid.uuid4())
        self.confd.set_users(MockUser(uuid=user_uuid, dnd_enabled=False))
        self.amid.set_queue_status(
            self._group_member(user_uuid, paused=True, queue='group1'),
            self._group_member(user_uuid, paused=False, queue='group2'),
        )

        self.bus.send_ami_fully_booted_event()

        self._assert_queue_pause(user_uuid, paused=False)

    def test_when_asterisk_restarts_then_member_paused_everywhere_is_left_alone(self):
        user_uuid = str(uuid.uuid4())
        sentinel_uuid = str(uuid.uuid4())
        self.confd.set_users(
            MockUser(uuid=user_uuid, dnd_enabled=True),
            MockUser(uuid=sentinel_uuid, dnd_enabled=True),
        )
        self.amid.set_queue_status(
            self._group_member(user_uuid, paused=True, queue='group1'),
            self._group_member(user_uuid, paused=True, queue='group2'),
            self._group_member(sentinel_uuid, paused=False),
        )

        self.bus.send_ami_fully_booted_event()
        self._wait_for_corrections(sentinel_uuid)

        self._assert_no_queue_pause(user_uuid)

    def test_when_a_correction_fails_then_the_other_members_are_corrected(self):
        failing_uuid = str(uuid.uuid4())
        other_uuid = str(uuid.uuid4())
        self.confd.set_users(
            MockUser(uuid=failing_uuid, dnd_enabled=True),
            MockUser(uuid=other_uuid, dnd_enabled=True),
        )
        self.amid.set_queue_status(
            self._group_member(failing_uuid, paused=False),
            self._group_member(other_uuid, paused=False),
        )
        self.amid.set_queue_pause_error(group_member_interface(failing_uuid))

        self.bus.send_ami_fully_booted_event()

        self._assert_queue_pause(other_uuid, paused=True)

    def test_when_asterisk_reboots_during_a_synchronization_then_it_runs_again(self):
        user_uuid = str(uuid.uuid4())
        self.confd.set_users(MockUser(uuid=user_uuid, dnd_enabled=True))
        self.amid.set_queue_status(self._group_member(user_uuid, paused=False))
        self.amid.set_queue_status_delay(5)

        self.bus.send_ami_fully_booted_event()
        self._wait_for_dnd_synchronization()

        self.amid.set_queue_status_delay(0)
        self.bus.send_ami_fully_booted_event()

        self._wait_for_dnd_synchronization(count=2)

    def test_when_a_dnd_event_fails_during_a_synchronization_then_it_is_corrected(self):
        user_uuid = str(uuid.uuid4())
        self.confd.set_users(MockUser(uuid=user_uuid, dnd_enabled=False))
        self.amid.set_queue_status(self._group_member(user_uuid, paused=True))
        self.amid.set_queue_pause_error(group_member_interface(user_uuid), paused=True)
        self.amid.set_queue_status_delay(5)

        self.bus.send_ami_fully_booted_event()
        self._wait_for_dnd_synchronization()

        self.bus.send_user_dnd_update(user_uuid, True)
        self._assert_queue_pause(user_uuid, paused=True)

        self._assert_queue_pause(user_uuid, paused=False)

    def test_when_calld_restarts_then_dnd_members_are_paused_again(self):
        user_uuid = str(uuid.uuid4())
        self.confd.set_users(MockUser(uuid=user_uuid, dnd_enabled=True))
        self.amid.set_queue_status(self._group_member(user_uuid, paused=False))

        self.restart_service('calld')
        self.reset_clients()
        self.wait_strategy.wait(self)

        self._assert_queue_pause(user_uuid, paused=True)
