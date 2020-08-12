# Copyright 2018-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


from hamcrest import (
    assert_that,
    calling,
    has_properties,
)
from xivo_test_helpers.hamcrest.raises import raises
from wazo_calld_client.exceptions import CalldError
from .helpers.real_asterisk import RealAsteriskIntegrationTest
from .helpers.constants import (
    SOME_CALL_ID,
)
from .helpers.real_asterisk import RealAsterisk


class TestAdhocConference(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def __init__(self):
        self.real_asterisk = RealAsterisk(self.ari)

    def test_user_create_adhoc_conference_no_auth(self):
        calld_no_auth = self.make_calld(token=None)
        assert_that(calling(calld_no_auth.adhoc_conferences.create_from_user)
                    .with_args(SOME_CALL_ID, SOME_CALL_ID),
                    raises(CalldError).matching(has_properties(status_code=401)))

    def test_user_create_adhoc_conference_no_host_call(self):
        caller_call_id, callee_call_id = self.real_asterisk.given_bridged_call_stasis()

        assert_that(calling(self.calld_client.adhoc_conferences.create_from_user)
                    .with_args(SOME_CALL_ID, callee_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'host-call-not-found',
                    })))

    def test_user_create_adhoc_conference_no_participant_call(self):
        caller_call_id, callee_call_id = self.real_asterisk.given_bridged_call_stasis()

        assert_that(calling(self.calld_client.adhoc_conferences.create_from_user)
                    .with_args(caller_call_id, SOME_CALL_ID),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'participant-call-not-found',
                    })))
