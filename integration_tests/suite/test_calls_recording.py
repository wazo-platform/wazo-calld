# Copyright 2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import uuid

from hamcrest import (
    assert_that,
    calling,
    has_entries,
    has_items,
    has_properties,
)
from wazo_calld_client.exceptions import CalldError
from xivo_test_helpers import until
from xivo_test_helpers.hamcrest.raises import raises

from .helpers.auth import MockUserToken
from .helpers.constants import ENDPOINT_AUTOANSWER
from .helpers.real_asterisk import RealAsteriskIntegrationTest

UNKNOWN_UUID = '00000000-0000-0000-0000-000000000000'


class TestCallRecord(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def test_put_record_start(self):
        channel_id = self.given_call_not_stasis()

        assert_that(
            calling(self.calld_client.calls.start_record).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404))
        )

        routing_key = 'calls.*.updated'
        event_accumulator = self.bus.accumulator(routing_key)

        self.calld_client.calls.start_record(channel_id)

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                has_items(has_entries(
                    name='call_updated',
                    data=has_entries(call_id=channel_id, record_state='active')
                ))
            )

        until.assert_(event_received, tries=3)

        assert_that(
            self.calld_client.calls.list_calls()['items'],
            has_items(has_entries(call_id=channel_id, record_state='active'))
        )

        # Only possible to record the same call once
        assert_that(
            calling(self.calld_client.calls.start_record).with_args(channel_id),
            raises(CalldError).matching(has_properties(status_code=400))
        )

    def test_put_record_start_from_user(self):
        user_uuid = str(uuid.uuid4())
        token = self.given_user_token(user_uuid)
        self.calld_client.set_token(token)
        channel_id = self.given_call_not_stasis(user_uuid=user_uuid)
        other_channel_id = self.given_call_not_stasis()

        assert_that(
            calling(self.calld_client.calls.start_record_from_user).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404))
        )
        assert_that(
            calling(self.calld_client.calls.start_record_from_user).with_args(other_channel_id),
            raises(CalldError).matching(has_properties(status_code=403))
        )

        routing_key = 'calls.*.updated'
        event_accumulator = self.bus.accumulator(routing_key)

        self.calld_client.calls.start_record_from_user(channel_id)

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                has_items(has_entries(
                    name='call_updated',
                    data=has_entries(call_id=channel_id, record_state='active')
                ))
            )

        until.assert_(event_received, tries=3)

        assert_that(
            self.calld_client.calls.list_calls_from_user()['items'],
            has_items(has_entries(call_id=channel_id, record_state='active'))
        )

        # Only possible to record the same call once
        assert_that(
            calling(self.calld_client.calls.start_record_from_user).with_args(channel_id),
            raises(CalldError).matching(has_properties(status_code=400))
        )

    def test_put_record_stop(self):
        channel_id = self.given_call_not_stasis()

        assert_that(
            calling(self.calld_client.calls.stop_record).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404))
        )
        routing_key = 'calls.*.updated'
        event_accumulator = self.bus.accumulator(routing_key)

        self.calld_client.calls.stop_record(channel_id)

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                has_items(has_entries(
                    name='call_updated',
                    data=has_entries(call_id=channel_id, record_state='inactive')
                ))
            )

        until.assert_(event_received, tries=3)

        assert_that(
            self.calld_client.calls.list_calls()['items'],
            has_items(has_entries(call_id=channel_id, record_state='inactive')),
        )

    def test_put_record_stop_from_user(self):
        user_uuid = str(uuid.uuid4())
        token = self.given_user_token(user_uuid)
        self.calld_client.set_token(token)
        channel_id = self.given_call_not_stasis(user_uuid=user_uuid)
        other_channel_id = self.given_call_not_stasis()

        assert_that(
            calling(self.calld_client.calls.stop_record_from_user).with_args(UNKNOWN_UUID),
            raises(CalldError).matching(has_properties(status_code=404))
        )
        assert_that(
            calling(self.calld_client.calls.stop_record_from_user).with_args(other_channel_id),
            raises(CalldError).matching(has_properties(status_code=403))
        )

        routing_key = 'calls.*.updated'
        event_accumulator = self.bus.accumulator(routing_key)

        self.calld_client.calls.stop_record_from_user(channel_id)

        def event_received():
            events = event_accumulator.accumulate()
            assert_that(
                events,
                has_items(has_entries(
                    name='call_updated',
                    data=has_entries(call_id=channel_id, record_state='inactive')
                ))
            )

        until.assert_(event_received, tries=3)

        assert_that(
            self.calld_client.calls.list_calls_from_user()['items'],
            has_items(has_entries(call_id=channel_id, record_state='inactive'))
        )

    def given_call_not_stasis(self, user_uuid=None):
        user_uuid = user_uuid or str(uuid.uuid4())
        call = self.ari.channels.originate(
            endpoint=ENDPOINT_AUTOANSWER,
            context='local',
            extension='dial-autoanswer',
            variables={'variables': {'XIVO_USERUUID': user_uuid}}
        )
        return call.id

    def given_user_token(self, user_uuid):
        token = 'my-token'
        self.auth.set_token(MockUserToken(token, user_uuid=user_uuid))
        return token
