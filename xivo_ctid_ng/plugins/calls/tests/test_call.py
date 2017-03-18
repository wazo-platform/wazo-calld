# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that, has_entries
from mock import sentinel as s
from unittest import TestCase

from ..call import Call
from ..schema import call_schema


class TestCall(TestCase):

    def test_to_dict(self):
        call = Call(s.call_id)
        call.creation_time = s.creation_time
        call.bridges = s.bridges
        call.status = s.status
        call.talking_to = s.talking_to
        call.user_uuid = s.user_uuid

        assert_that(call_schema.dump(call).data, has_entries({
            'bridges': [u'{}'.format(s.bridges)],
            'call_id': '{}'.format(s.call_id),
            'creation_time': '{}'.format(s.creation_time),
            'status': '{}'.format(s.status),
            'talking_to': s.talking_to,
            'user_uuid': '{}'.format(s.user_uuid),
        }))
