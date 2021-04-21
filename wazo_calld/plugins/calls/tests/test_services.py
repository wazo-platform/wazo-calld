# Copyright 2017-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from collections import defaultdict
from hamcrest import assert_that, has_properties
from mock import Mock
from unittest import TestCase

from ..services import CallsService


class TestServices(TestCase):

    def setUp(self):
        self.services = CallsService(Mock(), Mock(), Mock(), Mock(), Mock(), Mock(), Mock())

    def test_given_no_chan_variables_when_make_call_from_ami_event_then_call_has_none_values(self):
        event = defaultdict(str)
        event['ChanVariable'] = {}

        call = self.services.make_call_from_ami_event(event)

        assert_that(call, has_properties({
            'user_uuid': None,
            'dialed_extension': None,
        }))

    def test_given_xivo_useruuid_when_make_call_from_ami_event_then_call_has_useruuid(self):
        event = defaultdict(str)
        event['ChanVariable'] = {
            'XIVO_USERUUID': 'my-user-uuid',
        }

        call = self.services.make_call_from_ami_event(event)

        assert_that(call, has_properties({
            'user_uuid': 'my-user-uuid',
        }))

    def test_given_wazo_dereferenced_useruuid_when_make_call_from_ami_event_then_override_xivo_useruuid(self):
        event = defaultdict(str)
        event['ChanVariable'] = {
            'XIVO_USERUUID': 'my-user-uuid',
            'WAZO_DEREFERENCED_USERUUID': 'new-user-uuid',
        }

        call = self.services.make_call_from_ami_event(event)

        assert_that(call, has_properties({
            'user_uuid': 'new-user-uuid',
        }))
