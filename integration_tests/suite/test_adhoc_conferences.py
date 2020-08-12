# Copyright 2018-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import uuid

from ari.exceptions import ARINotInStasis
from hamcrest import (
    assert_that,
    calling,
    has_properties,
)
from xivo_test_helpers.hamcrest.raises import raises
from xivo_test_helpers import until
from wazo_calld_client.exceptions import CalldError
from .helpers.base import RealAsteriskIntegrationTest
from .helpers.constants import (
    ENDPOINT_AUTOANSWER,
    SOME_CALL_ID,
    SOME_STASIS_APP,
    SOME_STASIS_APP_INSTANCE
)


def make_user_uuid():
    return str(uuid.uuid4())


class TestAdhocConference(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def add_channel_to_bridge(self, bridge):
        def channel_is_in_stasis(channel_id):
            try:
                self.ari.channels.setChannelVar(channelId=channel_id, variable='TEST_STASIS', value='')
                return True
            except ARINotInStasis:
                return False

        new_channel = self.ari.channels.originate(endpoint=ENDPOINT_AUTOANSWER,
                                                  app=SOME_STASIS_APP,
                                                  appArgs=[SOME_STASIS_APP_INSTANCE])
        until.true(channel_is_in_stasis, new_channel.id, tries=2)
        bridge.addChannel(channel=new_channel.id)

        return new_channel

    def given_bridged_call_stasis(self, caller_uuid=None, callee_uuid=None):
        caller_uuid = caller_uuid or make_user_uuid()
        callee_uuid = callee_uuid or make_user_uuid()
        bridge = self.ari.bridges.create(type='mixing')
        caller = self.add_channel_to_bridge(bridge)
        caller.setChannelVar(variable='XIVO_USERUUID', value=caller_uuid)
        callee = self.add_channel_to_bridge(bridge)
        callee.setChannelVar(variable='XIVO_USERUUID', value=callee_uuid)

        def channels_have_been_created_in_calld(caller_id, callee_id):
            calls = self.calld_client.calls.list_calls(
                application=SOME_STASIS_APP,
                application_instance=SOME_STASIS_APP_INSTANCE,
            )
            channel_ids = [call['call_id'] for call in calls['items']]
            return (caller_id in channel_ids and callee_id in channel_ids)

        until.true(channels_have_been_created_in_calld, callee.id, caller.id, tries=3)

        return caller.id, callee.id

    def test_user_create_adhoc_conference_no_auth(self):
        calld_no_auth = self.make_calld(token=None)
        assert_that(calling(calld_no_auth.adhoc_conferences.create_from_user)
                    .with_args(SOME_CALL_ID, SOME_CALL_ID),
                    raises(CalldError).matching(has_properties(status_code=401)))

    def test_user_create_adhoc_conference_no_host_call(self):
        caller_call_id, callee_call_id = self.given_bridged_call_stasis()

        assert_that(calling(self.calld_client.adhoc_conferences.create_from_user)
                    .with_args(SOME_CALL_ID, callee_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'host-call-not-found',
                    })))

    def test_user_create_adhoc_conference_no_participant_call(self):
        caller_call_id, callee_call_id = self.given_bridged_call_stasis()

        assert_that(calling(self.calld_client.adhoc_conferences.create_from_user)
                    .with_args(caller_call_id, SOME_CALL_ID),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'participant-call-not-found',
                    })))
