# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase

from hamcrest import assert_that, calling, has_entries, raises
from marshmallow import ValidationError

from ..schemas import endpoint_list_params_schema, trunk_endpoint_schema


class TestTrunkEndpointSchema(TestCase):
    def test_uninitialized_fields(self):
        minimal_body = {
            'id': 42,
            'name': 'my-endpoint',
            'type': 'trunk',
        }

        result = trunk_endpoint_schema.dump(minimal_body)

        assert_that(
            result,
            has_entries(
                id=42,
                name='my-endpoint',
                type='trunk',
                technology='unknown',
                registered=None,
                current_call_count=None,
            ),
        )

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

        assert_that(
            result,
            has_entries(
                id=42,
                name='my-endpoint',
                type='trunk',
                technology='sip',
                registered=True,
                current_call_count=0,
            ),
        )


class TestEndpointListParamsSchema(TestCase):
    def test_defaults(self):
        result = endpoint_list_params_schema.load({})

        assert_that(result, has_entries(order='name', direction='asc', offset=0))

    def test_search_is_ignored(self):
        result = endpoint_list_params_schema.load({'search': 'foo', 'limit': '2'})

        assert_that(result, has_entries(limit=2))
        assert 'search' not in result

    def test_invalid_order(self):
        assert_that(
            calling(endpoint_list_params_schema.load).with_args({'order': 'tenant'}),
            raises(ValidationError),
        )

    def test_invalid_limit(self):
        assert_that(
            calling(endpoint_list_params_schema.load).with_args({'limit': '0'}),
            raises(ValidationError),
        )
