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
from .helpers.base import RealAsteriskIntegrationTest

SOME_CHANNEL_ID = '123456789.123'


def make_user_uuid():
    return str(uuid.uuid4())


class TestAdhocConference(RealAsteriskIntegrationTest):

    asset = 'real_asterisk_conference'

    def test_user_create_adhoc_conference_no_auth(self):
        calld_no_auth = self.make_calld(token=None)
        body = {
            'host_call_id': SOME_CHANNEL_ID,
            'participant_call_ids': [
                SOME_CHANNEL_ID,
            ],
        }
        assert_that(calling(calld_no_auth.adhoc_conferences.create_from_user).with_args(body),
                    raises(CalldError).matching(has_properties(status_code=401)))
