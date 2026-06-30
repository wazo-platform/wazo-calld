# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase

from hamcrest import assert_that, equal_to

from ..ari_ import DEFAULT_ARI_POOL_SIZE, ARIClientProxy, _build_ari_http_client


class TestBuildAriHttpClient(TestCase):
    def test_adapter_uses_configured_pool_size(self):
        http_client = _build_ari_http_client(
            'http://localhost:5039', 'xivo', 'secret', pool_size=25
        )

        adapter = http_client.session.get_adapter('http://localhost:5039')
        assert_that(adapter._pool_maxsize, equal_to(25))


class TestARIClientProxyPoolSize(TestCase):
    def test_default_pool_size(self):
        proxy = ARIClientProxy('http://localhost:5039', 'xivo', 'secret')

        assert_that(proxy._pool_size, equal_to(DEFAULT_ARI_POOL_SIZE))

    def test_explicit_pool_size(self):
        proxy = ARIClientProxy('http://localhost:5039', 'xivo', 'secret', pool_size=42)

        assert_that(proxy._pool_size, equal_to(42))
