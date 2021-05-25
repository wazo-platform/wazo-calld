# Copyright 2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import (
    assert_that,
    equal_to,
    has_key,
    has_entry,
)

from .helpers.base import IntegrationTest
from .helpers.base import VALID_TOKEN
from .helpers.wait_strategy import NoWaitStrategy


class TestConfig(IntegrationTest):

    asset = 'basic_rest'
    wait_strategy = NoWaitStrategy()

    def test_config(self):
        calld = self.make_calld(VALID_TOKEN)

        result = calld.config.get()

        assert_that(result, has_key('rest_api'))

    def test_update_config(self):
        calld = self.make_calld(VALID_TOKEN)

        debug_true_config = [
            {
                'op': 'replace',
                'path': '/debug',
                'value': True,
            }
        ]
        debug_false_config = [
            {
                'op': 'replace',
                'path': '/debug',
                'value': False,
            }
        ]

        debug_true_patched_config = calld.config.patch(debug_true_config)
        debug_true_config = calld.config.get()
        assert_that(debug_true_config, has_entry('debug', True))
        assert_that(debug_true_patched_config, equal_to(debug_true_config))

        debug_false_patched_config = calld.config.patch(debug_false_config)
        debug_false_config = calld.config.get()
        assert_that(debug_false_config, has_entry('debug', False))
        assert_that(debug_false_patched_config, equal_to(debug_false_config))
