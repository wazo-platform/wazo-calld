# Copyright 2018-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


import uuid

from hamcrest import (
    anything,
    assert_that,
    calling,
    has_entries,
    has_properties,
)
from xivo_test_helpers.hamcrest.raises import raises
from xivo_test_helpers import until
from wazo_calld_client.exceptions import CalldError
from .helpers.auth import MockUserToken
from .helpers.base import make_user_uuid
from .helpers.real_asterisk import RealAsteriskIntegrationTest
from .helpers.constants import (
    SOME_CALL_ID,
    VALID_TOKEN,
)
from .helpers.hamcrest_ import HamcrestARIChannel
from .helpers.real_asterisk import RealAsterisk


class TestAdhocConference(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def setUp(self):
        super().setUp()
        self.c = HamcrestARIChannel(self.ari)
        calld_client = self.make_calld(token=VALID_TOKEN)
        self.real_asterisk = RealAsterisk(self.ari, calld_client)

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

    def test_user_create_adhoc_conference_correct(self):
        user_uuid = make_user_uuid()
        token = self.make_user_token(user_uuid)
        self.calld_client.set_token(token)

        host_call1_id, participant1_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=user_uuid)
        host_call2_id, participant2_call_id = self.real_asterisk.given_bridged_call_stasis(caller_uuid=user_uuid)

        adhoc_conference = self.calld_client.adhoc_conferences.create_from_user(
            host_call1_id,
            participant1_call_id,
            participant2_call_id,
        )

        assert_that(adhoc_conference, has_entries({
            'conference_id': anything(),
        }))

        def calls_are_bridged():
            host_call1 = self.calld_client.calls.get_call(host_call1_id)
            assert_that(host_call1, has_entries({
                'talking_to': has_entries({
                    participant1_call_id: anything(),
                    participant2_call_id: anything(),
                })
            }))
            assert_that(host_call2_id, self.c.is_hungup())
        until.assert_(calls_are_bridged, timeout=10)
        # todo: expect bus event

    def test_user_create_adhoc_conference_participant_in_conference(self):
        pass

    def test_user_create_adhoc_conference_participant_is_lone_channel(self):
        pass

    def test_user_create_adhoc_conference_participant_not_in_stasis(self):
        pass

    def test_user_create_adhoc_conference_participant_not_talking_to_host(self):
        pass

    def test_user_create_adhoc_conference_participant_ringing(self):
        pass

    def test_user_create_adhoc_conference_host_not_talking_to_participant(self):
        pass

    def test_extra_participant_hangup(self):
        pass

    def test_last_participant_hangup(self):
        pass

    def test_host_hangup(self):
        pass
