# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import (
    assert_that,
    has_entry
)
from unittest import TestCase

from ..call import Call
from ..schema import CallSchema


class Testclassname(TestCase):

    def test_given_peer_caller_id_number_empty_when_dump_then_dialed_extension(self):
        call = Call('some-id')
        call.dialed_extension = 'dialed_extension'

        result = CallSchema().dump(call).data

        assert_that(result, has_entry('peer_caller_id_number', 'dialed_extension'))

    def test_given_peer_caller_id_number_when_dump_then_peer_caller_id_number(self):
        call = Call('some-id')
        call.peer_caller_id_number = 'caller_id_number'
        call.dialed_extension = 'dialed_extension'

        result = CallSchema().dump(call).data

        assert_that(result, has_entry('peer_caller_id_number', 'caller_id_number'))
