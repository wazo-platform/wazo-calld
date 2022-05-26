# Copyright 2019-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import (
    assert_that,
    equal_to,
    calling,
    raises,
)
from unittest.mock import Mock
from unittest import TestCase

from ..confd_client_cache import ConfdClientGetUUIDCacheDecorator


class TestConfdCacheGetUUID(TestCase):
    def setUp(self):
        self.mock_get = Mock()
        self.cache_get = ConfdClientGetUUIDCacheDecorator(
            self.mock_get, resource_name='test'
        )

    def test_get(self):
        # test first get
        self.mock_get.return_value = 'some-response'

        result = self.cache_get('some-uuid')

        # test second get, not invalidated
        self.mock_get.return_value = 'some-new-response'

        result = self.cache_get('some-uuid')

        assert_that(result, equal_to('some-response'))

    def test_get_passes_all_arguments_to_client(self):
        self.cache_get('some-uuid', 'some-arg', kwarg='some-kwarg')

        self.mock_get.assert_called_once_with(
            'some-uuid', 'some-arg', kwarg='some-kwarg'
        )

    def test_get_with_different_args_returns_different_results(self):
        class NoSuchResource(Exception):
            pass

        self.mock_get.return_value = 'some-response'
        self.cache_get('some-uuid', tenant_uuid='tenant1')
        self.mock_get.side_effect = NoSuchResource()

        assert_that(
            calling(self.cache_get).with_args('some-uuid', tenant_uuid='tenant2'),
            raises(NoSuchResource),
        )

    def test_invalidate(self):
        self.mock_get.return_value = 'some-response'
        result = self.cache_get('some-uuid')
        self.mock_get.return_value = 'some-new-response'

        self.cache_get.invalidate_cache_entry('some-uuid')

        result = self.cache_get('some-uuid')
        assert_that(result, equal_to('some-new-response'))

    def test_invalidate_unknown_entry(self):
        try:
            self.cache_get.invalidate_cache_entry('some-uuid')
        except KeyError:
            self.fail('invalidate_cache_entry raised KeyError')
