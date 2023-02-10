# Copyright 2021-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import uuid

from hamcrest import (
    assert_that,
    calling,
    has_entries,
    has_items,
    has_properties,
    not_,
)
from wazo_calld_client.exceptions import CalldError
from wazo_test_helpers import until
from wazo_test_helpers.hamcrest.raises import raises

from .helpers.auth import MockUserToken
from .helpers.constants import ENDPOINT_AUTOANSWER, VALID_TENANT
from .helpers.real_asterisk import RealAsteriskIntegrationTest

UNKNOWN_UUID = '00000000-0000-0000-0000-000000000000'


class TestCallRecord(RealAsteriskIntegrationTest):
    asset = 'real_asterisk'

    def test_put_record_start(self):
        channel_id = self.given_call_not_stasis()
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
        token = self.given_user_token(user_uuid)
        self.calld_client.set_token(token)
        channel_id = self.given_call_not_stasis(user_uuid=user_uuid)
        events = self.bus.accumulator(headers={'name': 'call_updated'})

        self.calld_client.calls.start_record_from_user(channel_id)

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
            self.calld_client.calls.list_calls_from_user()['items'],
            has_items(has_entries(call_id=channel_id, record_state='active')),
        )

        # Should not raise an error on second record start
        assert_that(
            calling(self.calld_client.calls.start_record_from_user).with_args(
                channel_id
            ),
            not_(raises(CalldError)),
        )

    def test_put_record_start_from_user_errors(self):
        user_uuid = str(uuid.uuid4())
        token = self.given_user_token(user_uuid)
        self.calld_client.set_token(token)
        other_channel_id = self.given_call_not_stasis()
        assert_that(
            calling(self.calld_client.calls.start_record_from_user).with_args(
                UNKNOWN_UUID
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.calls.start_record_from_user).with_args(
                other_channel_id
            ),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

    def test_put_record_stop(self):
        channel_id = self.given_call_not_stasis()

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
        token = self.given_user_token(user_uuid)
        self.calld_client.set_token(token)
        channel_id = self.given_call_not_stasis(user_uuid=user_uuid)
        other_channel_id = self.given_call_not_stasis()

        assert_that(
            calling(self.calld_client.calls.stop_record_from_user).with_args(
                UNKNOWN_UUID
            ),
            raises(CalldError).matching(has_properties(status_code=404)),
        )
        assert_that(
            calling(self.calld_client.calls.stop_record_from_user).with_args(
                other_channel_id
            ),
            raises(CalldError).matching(has_properties(status_code=403)),
        )

        events = self.bus.accumulator(headers={'name': 'call_updated'})

        self.calld_client.calls.stop_record_from_user(channel_id)

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
            self.calld_client.calls.list_calls_from_user()['items'],
            has_items(has_entries(call_id=channel_id, record_state='inactive')),
        )

        # Should not raise an error on second record stop
        assert_that(
            calling(self.calld_client.calls.stop_record_from_user).with_args(
                channel_id
            ),
            not_(raises(CalldError)),
        )

    def given_call_not_stasis(self, user_uuid=None, variables=None):
        user_uuid = user_uuid or str(uuid.uuid4())
        variables = variables or {}
        variables.setdefault('XIVO_USERUUID', user_uuid)
        variables.setdefault('WAZO_TENANT_UUID', VALID_TENANT)
        variables.setdefault('WAZO_CALL_RECORD_SIDE', 'caller')
        call = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            context='local',
            extension='dial-autoanswer',
            variables={'variables': variables},
        )
        return call.id

    def given_user_token(self, user_uuid):
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        return token
