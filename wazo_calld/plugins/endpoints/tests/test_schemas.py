# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase

from hamcrest import (
    assert_that,
    has_entries,
)

from ..schemas import trunk_endpoint_schema


class TestTrunkEndpointSchema(TestCase):
    def test_uninitialized_fields(self):
        minimal_body = {
            'id': 42,
            'name': 'my-endpoint',
            'type': 'trunk',
        }

        result = trunk_endpoint_schema.dump(minimal_body)

        assert_that(result, has_entries(
            id=42,
            name='my-endpoint',
            type='trunk',
            technology='unknown',
            registered=None,
            current_call_count=None,
        ))

    def test_all_fields(self):
        minimal_body = {
            'id': 42,
            'name': 'my-endpoint',
            'type': 'trunk',
            'technology': 'sip',
            'registered': True,
            'current_call_count': 0,
        }

        result = trunk_endpoint_schema.dump(minimal_body)

        assert_that(result, has_entries(
            id=42,
            name='my-endpoint',
            type='trunk',
            technology='sip',
            registered=True,
            current_call_count=0,
        ))
