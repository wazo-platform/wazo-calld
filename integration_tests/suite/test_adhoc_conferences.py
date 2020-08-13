# Copyright 2018-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


import uuid

from hamcrest import (
    assert_that,
    calling,
    has_properties,
)
from xivo_test_helpers.hamcrest.raises import raises
from wazo_calld_client.exceptions import CalldError
from .helpers.auth import MockUserToken
from .helpers.base import make_user_uuid
from .helpers.real_asterisk import RealAsteriskIntegrationTest
from .helpers.constants import (
    SOME_CALL_ID,
)
from .helpers.real_asterisk import RealAsterisk


class TestAdhocConference(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def setUp(self):
        super().setUp()
        self.real_asterisk = RealAsterisk(self.ari, self.calld_client)

    def make_user_token(self, user_uuid, tenant_uuid=None):
        token_id = str(uuid.uuid4())
        tenant_uuid = tenant_uuid or str(uuid.uuid4())
        self.auth.set_token(MockUserToken(token_id, tenant_uuid=tenant_uuid, user_uuid=user_uuid))
        return token_id

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

    def test_user_create_adhoc_conference_user_does_not_own_host_call(self):
        user_uuid = make_user_uuid()
        another_user_uuid = make_user_uuid()
        token = self.make_user_token(user_uuid)

        self.calld_client.set_token(token)
        host_call_id, participant_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=another_user_uuid)

        assert_that(calling(self.calld_client.adhoc_conferences.create_from_user)
                    .with_args(host_call_id, participant_call_id),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'host-call-permission-denied',
                    })))

    def test_user_create_adhoc_conference_invalid_request(self):
        assert_that(calling(self.calld_client.adhoc_conferences.create_from_user)
                    .with_args(None, None),
                    raises(CalldError).matching(has_properties({
                        'status_code': 400,
                        'error_id': 'invalid-data',
                    })))
