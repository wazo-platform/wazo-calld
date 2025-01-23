# Copyright 2021-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import uuid

import pytest
from hamcrest import assert_that, calling, has_entries, has_items, has_properties, not_
from wazo_calld_client.exceptions import CalldError
from wazo_test_helpers import until
from wazo_test_helpers.hamcrest.raises import raises

from .helpers.constants import ENDPOINT_AUTOANSWER, VALID_TENANT
from .helpers.real_asterisk import RealAsteriskIntegrationTest

UNKNOWN_UUID = '00000000-0000-0000-0000-000000000000'


class TestCallRecord(RealAsteriskIntegrationTest):
    asset = 'real_asterisk'

    def test_put_record_start_user_allowed(self):
        channel_id = self.given_call_not_stasis(
            variables={'WAZO_USER_DTMF_RECORD_TOGGLE_ENABLED': '1'}
        )
        call_events = self.bus.accumulator(headers={'name': 'call_updated'})
        recording_events = self.bus.accumulator(headers={'name': 'recording_started'})

        self.calld_client.calls.start_record(channel_id)

        def event_received():
            assert_that(
                call_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(call_id=channel_id, record_state='active'),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(event_received, tries=10)

        def recording_event_received():
            assert_that(
                recording_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='recording_started',
                            data=has_entries(call_id=channel_id),
                        ),
                        headers=has_entries(
                            name='recording_started',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(recording_event_received, tries=10)

        assert_that(
            self.calld_client.calls.list_calls()['items'],
            has_items(has_entries(call_id=channel_id, record_state='active')),
        )

        # Should not raise an error on second record start
        assert_that(
            calling(self.calld_client.calls.start_record).with_args(channel_id),
            not_(raises(CalldError)),
        )

    def test_put_record_start_queue_allowed(self):
        channel_id = self.given_call_not_stasis(
            variables={
                'WAZO_QUEUE_DTMF_RECORD_TOGGLE_ENABLED': '1',
                'WAZO_QUEUENAME': 'q',
                'WAZO_CALL_RECORD_SIDE': '',  # callee
            },
        )
        call_events = self.bus.accumulator(headers={'name': 'call_updated'})
        recording_events = self.bus.accumulator(headers={'name': 'recording_started'})

        self.calld_client.calls.start_record(channel_id)

        def event_received():
            assert_that(
                call_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(call_id=channel_id, record_state='active'),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(event_received, tries=10)

        def recording_event_received():
            assert_that(
                recording_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='recording_started',
                            data=has_entries(call_id=channel_id),
                        ),
                        headers=has_entries(
                            name='recording_started',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(recording_event_received, tries=10)

        assert_that(
            self.calld_client.calls.list_calls()['items'],
            has_items(has_entries(call_id=channel_id, record_state='active')),
        )

        # Should not raise an error on second record start
        assert_that(
            calling(self.calld_client.calls.start_record).with_args(channel_id),
            not_(raises(CalldError)),
        )

    def test_put_record_start_group_allowed(self):
        channel_id = self.given_call_not_stasis(
            variables={
                'WAZO_GROUP_DTMF_RECORD_TOGGLE_ENABLED': '1',
                'WAZO_GROUPNAME': 'g',
                'WAZO_CALL_RECORD_SIDE': '',  # callee
            },
        )
        call_events = self.bus.accumulator(headers={'name': 'call_updated'})
        recording_events = self.bus.accumulator(headers={'name': 'recording_started'})

        self.calld_client.calls.start_record(channel_id)

        def event_received():
            assert_that(
                call_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(call_id=channel_id, record_state='active'),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(event_received, tries=10)

        def recording_event_received():
            assert_that(
                recording_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='recording_started',
                            data=has_entries(call_id=channel_id),
                        ),
                        headers=has_entries(
                            name='recording_started',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(recording_event_received, tries=10)

        assert_that(
            self.calld_client.calls.list_calls()['items'],
            has_items(has_entries(call_id=channel_id, record_state='active')),
        )

        # Should not raise an error on second record start
        assert_that(
            calling(self.calld_client.calls.start_record).with_args(channel_id),
            not_(raises(CalldError)),
        )

    def test_put_record_start_errors(self):
        assert_that(
            calling(self.calld_client.calls.start_record).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

        # No user permission
        channel_id = self.given_call_not_stasis()
        assert_that(
            calling(self.calld_client.calls.start_record).with_args(channel_id),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

        # No queue permission
        channel_id = self.given_call_not_stasis(
            variables={'WAZO_QUEUENAME': 'q', 'WAZO_CALL_RECORD_SIDE': ''}
        )
        assert_that(
            calling(self.calld_client.calls.start_record).with_args(channel_id),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

        # No group permission
        channel_id = self.given_call_not_stasis(
            variables={'WAZO_GROUPNAME': 'g', 'WAZO_CALL_RECORD_SIDE': ''}
        )
        assert_that(
            calling(self.calld_client.calls.start_record).with_args(channel_id),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

        # Queue permission but no user permission for caller
        channel_id = self.given_call_not_stasis(
            variables={
                'WAZO_QUEUENAME': 'q',
                'WAZO_CALL_RECORD_SIDE': 'caller',
                'WAZO_QUEUE_DTMF_RECORD_TOGGLE_ENABLED': '1',
            }
        )
        assert_that(
            calling(self.calld_client.calls.start_record).with_args(channel_id),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

        # Group permission but no user permission for caller
        channel_id = self.given_call_not_stasis(
            variables={
                'WAZO_GROUPNAME': 'g',
                'WAZO_CALL_RECORD_SIDE': 'caller',
                'WAZO_GROUP_DTMF_RECORD_TOGGLE_ENABLED': '1',
            }
        )
        assert_that(
            calling(self.calld_client.calls.start_record).with_args(channel_id),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

    def test_put_record_start_from_user(self):
        user_uuid = str(uuid.uuid4())
        channel_id = self.given_call_not_stasis(
            user_uuid=user_uuid, variables={'WAZO_USER_DTMF_RECORD_TOGGLE_ENABLED': '1'}
        )
        call_events = self.bus.accumulator(headers={'name': 'call_updated'})
        recording_events = self.bus.accumulator(headers={'name': 'recording_started'})
        user_calld = self.make_user_calld(user_uuid, tenant_uuid=VALID_TENANT)

        user_calld.calls.start_record_from_user(channel_id)

        def event_received():
            assert_that(
                call_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(call_id=channel_id, record_state='active'),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(event_received, tries=10)

        def recording_event_received():
            assert_that(
                recording_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='recording_started',
                            data=has_entries(call_id=channel_id),
                        ),
                        headers=has_entries(
                            name='recording_started',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(recording_event_received, tries=10)

        assert_that(
            user_calld.calls.list_calls_from_user()['items'],
            has_items(has_entries(call_id=channel_id, record_state='active')),
        )

        # Should not raise an error on second record start
        assert_that(
            calling(user_calld.calls.start_record_from_user).with_args(channel_id),
            not_(raises(CalldError)),
        )

    def test_put_record_start_from_user_errors(self):
        user_uuid = str(uuid.uuid4())
        other_channel_id = self.given_call_not_stasis(
            variables={'WAZO_USER_DTMF_RECORD_TOGGLE_ENABLED': '1'}
        )
        user_calld = self.make_user_calld(user_uuid, tenant_uuid=VALID_TENANT)

        assert_that(
            calling(user_calld.calls.start_record_from_user).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(user_calld.calls.start_record_from_user).with_args(
                other_channel_id
            ),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

    def test_put_record_stop_user_allowed(self):
        channel_id = self.given_call_not_stasis(
            variables={'WAZO_USER_DTMF_RECORD_TOGGLE_ENABLED': '1'}
        )

        assert_that(
            calling(self.calld_client.calls.stop_record).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        call_events = self.bus.accumulator(headers={'name': 'call_updated'})
        recording_events = self.bus.accumulator(headers={'name': 'recording_stopped'})

        self.calld_client.calls.stop_record(channel_id)

        def event_received():
            assert_that(
                call_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(
                                call_id=channel_id, record_state='inactive'
                            ),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(event_received, tries=10)

        def recording_event_received():
            assert_that(
                recording_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='recording_stopped',
                            data=has_entries(call_id=channel_id),
                        ),
                        headers=has_entries(
                            name='recording_stopped',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(recording_event_received, tries=10)

        assert_that(
            self.calld_client.calls.list_calls()['items'],
            has_items(has_entries(call_id=channel_id, record_state='inactive')),
        )

        # Should not raise an error on second record stop
        assert_that(
            calling(self.calld_client.calls.stop_record).with_args(channel_id),
            not_(raises(CalldError)),
        )

    def test_put_record_stop_queue_allowed(self):
        channel_id = self.given_call_not_stasis(
            variables={
                'WAZO_QUEUE_DTMF_RECORD_TOGGLE_ENABLED': '1',
                'WAZO_QUEUENAME': 'q',
                'WAZO_CALL_RECORD_SIDE': '',  # callee
            },
        )

        assert_that(
            calling(self.calld_client.calls.stop_record).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        call_events = self.bus.accumulator(headers={'name': 'call_updated'})
        recording_events = self.bus.accumulator(headers={'name': 'recording_stopped'})

        self.calld_client.calls.stop_record(channel_id)

        def event_received():
            assert_that(
                call_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(
                                call_id=channel_id, record_state='inactive'
                            ),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(event_received, tries=10)

        def recording_event_received():
            assert_that(
                recording_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='recording_stopped',
                            data=has_entries(call_id=channel_id),
                        ),
                        headers=has_entries(
                            name='recording_stopped',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(recording_event_received, tries=10)

        assert_that(
            self.calld_client.calls.list_calls()['items'],
            has_items(has_entries(call_id=channel_id, record_state='inactive')),
        )

        # Should not raise an error on second record stop
        assert_that(
            calling(self.calld_client.calls.stop_record).with_args(channel_id),
            not_(raises(CalldError)),
        )

    def test_put_record_stop_group_allowed(self):
        channel_id = self.given_call_not_stasis(
            variables={
                'WAZO_GROUP_DTMF_RECORD_TOGGLE_ENABLED': '1',
                'WAZO_GROUPNAME': 'g',
                'WAZO_CALL_RECORD_SIDE': '',  # callee
            },
        )

        assert_that(
            calling(self.calld_client.calls.stop_record).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        call_events = self.bus.accumulator(headers={'name': 'call_updated'})
        recording_events = self.bus.accumulator(headers={'name': 'recording_stopped'})

        self.calld_client.calls.stop_record(channel_id)

        def event_received():
            assert_that(
                call_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(
                                call_id=channel_id, record_state='inactive'
                            ),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(event_received, tries=10)

        def recording_event_received():
            assert_that(
                recording_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='recording_stopped',
                            data=has_entries(call_id=channel_id),
                        ),
                        headers=has_entries(
                            name='recording_stopped',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(recording_event_received, tries=10)

        assert_that(
            self.calld_client.calls.list_calls()['items'],
            has_items(has_entries(call_id=channel_id, record_state='inactive')),
        )

        # Should not raise an error on second record stop
        assert_that(
            calling(self.calld_client.calls.stop_record).with_args(channel_id),
            not_(raises(CalldError)),
        )

    def test_put_record_stop_from_user(self):
        user_uuid = str(uuid.uuid4())
        channel_id = self.given_call_not_stasis(
            user_uuid=user_uuid, variables={'WAZO_USER_DTMF_RECORD_TOGGLE_ENABLED': '1'}
        )
        other_channel_id = self.given_call_not_stasis(
            variables={'WAZO_USER_DTMF_RECORD_TOGGLE_ENABLED': '1'}
        )
        user_calld = self.make_user_calld(user_uuid, tenant_uuid=VALID_TENANT)
        user_calld.calls.start_record_from_user(channel_id)

        call_events = self.bus.accumulator(headers={'name': 'call_updated'})
        recording_started_events = self.bus.accumulator(headers={'name': 'recording_started'})
        recording_stopped_events = self.bus.accumulator(headers={'name': 'recording_stopped'})

        def recording_started():
            assert_that(
                call_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(call_id=channel_id, record_state='active'),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(recording_started, tries=10)

        def recording_started_event_received():
            assert_that(
                recording_started_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='recording_started',
                            data=has_entries(call_id=channel_id),
                        ),
                        headers=has_entries(
                            name='recording_started',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(recording_started_event_received, tries=10)

        assert_that(
            calling(user_calld.calls.stop_record_from_user).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(user_calld.calls.stop_record_from_user).with_args(other_channel_id),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

        user_calld.calls.stop_record_from_user(channel_id)

        def event_received():
            assert_that(
                call_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(
                                call_id=channel_id, record_state='inactive'
                            ),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(event_received, tries=10)

        def recording_stopped_event_received():
            assert_that(
                recording_stopped_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='recording_stopped',
                            data=has_entries(call_id=channel_id),
                        ),
                        headers=has_entries(
                            name='recording_stopped',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(recording_stopped_event_received, tries=10)

        assert_that(
            user_calld.calls.list_calls_from_user()['items'],
            has_items(has_entries(call_id=channel_id, record_state='inactive')),
        )

        # Should not raise an error on second record stop
        assert_that(
            calling(user_calld.calls.stop_record_from_user).with_args(channel_id),
            not_(raises(CalldError)),
        )

    def test_put_record_pause(self):
        channel_id = self.given_call_not_stasis(
            variables={'WAZO_USER_DTMF_RECORD_TOGGLE_ENABLED': '1'}
        )
        call_events = self.bus.accumulator(headers={'name': 'call_updated'})
        recording_started_events = self.bus.accumulator(headers={'name': 'recording_started'})
        recording_paused_events = self.bus.accumulator(headers={'name': 'recording_paused'})

        self.calld_client.calls.start_record(channel_id)

        def recording_started():
            assert_that(
                call_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(call_id=channel_id, record_state='active'),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(recording_started, tries=10)

        def recording_started_event_received():
            assert_that(
                recording_started_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='recording_started',
                            data=has_entries(call_id=channel_id),
                        ),
                        headers=has_entries(
                            name='recording_started',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(recording_started_event_received, tries=10)

        self.calld_client.calls.pause_record(channel_id)

        def call_event_received():
            assert_that(
                call_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(call_id=channel_id, record_state='paused'),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(call_event_received, tries=10)

        def record_event_received():
            assert_that(
                recording_paused_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='recording_paused',
                            data=has_entries(call_id=channel_id),
                        ),
                        headers=has_entries(
                            name='recording_paused',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(record_event_received, tries=10)

        assert_that(
            self.calld_client.calls.list_calls()['items'],
            has_items(has_entries(call_id=channel_id, record_state='paused')),
        )

        # Should not raise an error on second record pause
        assert_that(
            calling(self.calld_client.calls.pause_record).with_args(channel_id),
            not_(raises(CalldError)),
        )

    def test_put_record_pause_errors(self):
        assert_that(
            calling(self.calld_client.calls.pause_record).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404)),
        )

    def test_put_record_pause_from_user(self):
        user_uuid = str(uuid.uuid4())
        channel_id = self.given_call_not_stasis(
            user_uuid=user_uuid,
            variables={'WAZO_USER_DTMF_RECORD_TOGGLE_ENABLED': '1'}
        )
        call_events = self.bus.accumulator(headers={'name': 'call_updated'})
        recording_paused_events = self.bus.accumulator(headers={'name': 'recording_paused'})
        recording_started_events = self.bus.accumulator(headers={'name': 'recording_started'})
        user_calld = self.make_user_calld(user_uuid, tenant_uuid=VALID_TENANT)

        user_calld.calls.start_record_from_user(channel_id)

        def recording_started():
            assert_that(
                call_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(call_id=channel_id, record_state='active'),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(recording_started, tries=10)

        def recording_started_event_received():
            assert_that(
                recording_started_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='recording_started',
                            data=has_entries(call_id=channel_id),
                        ),
                        headers=has_entries(
                            name='recording_started',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(recording_started_event_received, tries=10)

        user_calld.calls.pause_record_from_user(channel_id)

        def event_received():
            assert_that(
                call_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='call_updated',
                            data=has_entries(call_id=channel_id, record_state='paused'),
                        ),
                        headers=has_entries(
                            name='call_updated',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(event_received, tries=10)

        def record_event_received():
            assert_that(
                recording_paused_events.accumulate(with_headers=True),
                has_items(
                    has_entries(
                        message=has_entries(
                            name='recording_paused',
                            data=has_entries(call_id=channel_id),
                        ),
                        headers=has_entries(
                            name='recording_paused',
                            tenant_uuid=VALID_TENANT,
                        ),
                    )
                ),
            )

        until.assert_(record_event_received, tries=10)

        assert_that(
            user_calld.calls.list_calls_from_user()['items'],
            has_items(has_entries(call_id=channel_id, record_state='paused')),
        )

        # Should not raise an error on second record pause
        assert_that(
            calling(user_calld.calls.pause_record_from_user).with_args(channel_id),
            not_(raises(CalldError)),
        )

    def test_put_record_pause_from_user_errors(self):
        user_uuid = str(uuid.uuid4())
        other_channel_id = self.given_call_not_stasis(
            variables={'WAZO_USER_DTMF_RECORD_TOGGLE_ENABLED': '1'}
        )
        user_calld = self.make_user_calld(user_uuid, tenant_uuid=VALID_TENANT)

        assert_that(
            calling(user_calld.calls.pause_record_from_user).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(user_calld.calls.pause_record_from_user).with_args(
                other_channel_id
            ),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

    def test_put_record_tenant_isolation(self):
        user_uuid_1 = str(uuid.uuid4())
        tenant_uuid_1 = str(uuid.uuid4())
        tenant_uuid_2 = str(uuid.uuid4())
        channel_id_1 = self.given_call_not_stasis(
            tenant_uuid=tenant_uuid_1,
            variables={'WAZO_USER_DTMF_RECORD_TOGGLE_ENABLED': '1'},
        )
        channel_id_2 = self.given_call_not_stasis(
            tenant_uuid=tenant_uuid_2,
            variables={'WAZO_USER_DTMF_RECORD_TOGGLE_ENABLED': '1'},
        )
        user_calld = self.make_user_calld(user_uuid_1, tenant_uuid=tenant_uuid_1)

        # record channel from other tenant = NOK
        with pytest.raises(CalldError) as exc_info:
            user_calld.calls.start_record(channel_id_2)

        calld_error = exc_info.value
        assert calld_error.status_code == 404, calld_error

        with pytest.raises(CalldError) as exc_info:
            user_calld.calls.stop_record(channel_id_2)

        calld_error = exc_info.value
        assert calld_error.status_code == 404, calld_error

        # record channel from same tenant = OK
        user_calld.calls.start_record(channel_id_1)
        user_calld.calls.stop_record(channel_id_1)

    def given_call_not_stasis(self, user_uuid=None, variables=None, tenant_uuid=None):
        user_uuid = user_uuid or str(uuid.uuid4())
        tenant_uuid = tenant_uuid or VALID_TENANT
        variables = variables or {}
        variables.setdefault('WAZO_USERUUID', user_uuid)
        variables.setdefault('WAZO_TENANT_UUID', tenant_uuid)
        variables.setdefault('WAZO_CALL_RECORD_SIDE', 'caller')
        call = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            context='local',
            extension='dial-autoanswer',
            variables={'variables': variables},
        )
        return call.id
