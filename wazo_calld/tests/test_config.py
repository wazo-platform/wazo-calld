# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase

from hamcrest import assert_that, equal_to, has_key, not_
from xivo.chain_map import ChainMap

from ..config import _DEFAULT_CONFIG, _get_reinterpreted_raw_values


class TestAriPoolSizeDerivation(TestCase):
    def test_pool_size_defaults_to_max_threads(self):
        config = ChainMap({}, _DEFAULT_CONFIG)

        result = _get_reinterpreted_raw_values(config)

        assert_that(
            result['ari']['connection']['pool_size'],
            equal_to(_DEFAULT_CONFIG['rest_api']['max_threads']),
        )

    def test_pool_size_follows_configured_max_threads(self):
        file_config = {'rest_api': {'max_threads': 250}}
        config = ChainMap(file_config, _DEFAULT_CONFIG)

        result = _get_reinterpreted_raw_values(config)

        assert_that(result['ari']['connection']['pool_size'], equal_to(250))

    def test_explicit_pool_size_is_not_overridden(self):
        file_config = {'ari': {'connection': {'pool_size': 42}}}
        config = ChainMap(file_config, _DEFAULT_CONFIG)

        result = _get_reinterpreted_raw_values(config)

        assert_that(result, not_(has_key('ari')))

    def test_derived_overlay_keeps_other_connection_settings(self):
        config = ChainMap({}, _DEFAULT_CONFIG)
        overlay = _get_reinterpreted_raw_values(config)

        final = ChainMap(overlay, _DEFAULT_CONFIG)

        assert_that(
            final['ari']['connection']['base_url'],
            equal_to(_DEFAULT_CONFIG['ari']['connection']['base_url']),
        )
        assert_that(
            final['ari']['connection']['pool_size'],
            equal_to(_DEFAULT_CONFIG['rest_api']['max_threads']),
        )
