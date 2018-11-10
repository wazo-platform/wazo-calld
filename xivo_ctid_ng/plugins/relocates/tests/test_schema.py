# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import (
    assert_that,
    calling,
    has_entry,
    raises,
)
from marshmallow import ValidationError
from unittest import TestCase
from ..schema import user_relocate_request_schema

VALID_RELOCATE = {
    'initiator_call': '123456789.0',
    'destination': 'mobile',
}


class Testclassname(TestCase):

    def test_given_invalid_location_when_load_then_raise(self):
        relocate = dict(VALID_RELOCATE)
        relocate['destination'] = {'invalid': 'invalid'}

        assert_that(calling(user_relocate_request_schema.load).with_args(relocate),
                    raises(ValidationError))

    def test_given_mobile_destination_when_load_then_location_empty(self):
        relocate = dict(VALID_RELOCATE)
        relocate['destination'] = 'mobile'

        assert_that(user_relocate_request_schema.load(relocate).data,
                    has_entry('location', {}))

    def test_given_line_destination_when_load_then_validation_may_fail(self):
        relocate = dict(VALID_RELOCATE)
        relocate['destination'] = 'line'
        relocate['location'] = {'line_id': -12}

        assert_that(calling(user_relocate_request_schema.load).with_args(relocate),
                    raises(ValidationError))
