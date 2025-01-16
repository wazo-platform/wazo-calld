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

    def test_put_record_start(self):
        channel_id = self.given_call_not_stasis(
            variables={'WAZO_USER_DTMF_RECORD_TOGGLE_ENABLED': '1'}
        )
        events = self.bus.accumulator(headers={'name': 'call_updated'})

        self.calld_client.calls.start_record(channel_id)

        def event_received():
            assert_that(
                events.accumulate(with_headers=True),
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

    def test_put_record_start_from_user(self):
        user_uuid = str(uuid.uuid4())
        channel_id = self.given_call_not_stasis(
            user_uuid=user_uuid, variables={'WAZO_USER_DTMF_RECORD_TOGGLE_ENABLED': '1'}
        )
        events = self.bus.accumulator(headers={'name': 'call_updated'})
        user_calld = self.make_user_calld(user_uuid, tenant_uuid=VALID_TENANT)

        user_calld.calls.start_record_from_user(channel_id)

        def event_received():
            assert_that(
                events.accumulate(with_headers=True),
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

    def test_put_record_stop(self):
        channel_id = self.given_call_not_stasis(
            variables={'WAZO_USER_DTMF_RECORD_TOGGLE_ENABLED': '1'}
        )

        assert_that(
            calling(self.calld_client.calls.stop_record).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        events = self.bus.accumulator(headers={'name': 'call_updated'})

        self.calld_client.calls.stop_record(channel_id)

        def event_received():
            assert_that(
                events.accumulate(with_headers=True),
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

        events = self.bus.accumulator(headers={'name': 'call_updated'})

        def recording_started():
            assert_that(
                events.accumulate(with_headers=True),
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
                events.accumulate(with_headers=True),
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

        assert_that(
            user_calld.calls.list_calls_from_user()['items'],
            has_items(has_entries(call_id=channel_id, record_state='inactive')),
        )

        # Should not raise an error on second record stop
        assert_that(
            calling(user_calld.calls.stop_record_from_user).with_args(channel_id),
            not_(raises(CalldError)),
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
