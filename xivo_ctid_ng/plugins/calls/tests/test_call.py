# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that, has_entries
from mock import sentinel as s
from unittest import TestCase

from ..call import Call


class TestCall(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_to_dict(self):
        call = Call(s.call_id, s.creation_time)
        call.bridges = s.bridges
        call.status = s.status
        call.talking_to = s.talking_to
        call.user_uuid = s.user_uuid

        assert_that(call.to_dict(), has_entries({
            'bridges': s.bridges,
            'call_id': s.call_id,
            'creation_time': s.creation_time,
            'status': s.status,
            'talking_to': s.talking_to,
            'user_uuid': s.user_uuid,
        }))
