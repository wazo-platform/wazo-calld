# Copyright 2016-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests
from hamcrest import (
    assert_that,
    has_entries,
    has_entry,
)
from wazo_test_helpers import until


class WaitStrategy:
    def wait(self, integration_test):
        raise NotImplementedError()


class NoWaitStrategy(WaitStrategy):
    def wait(self, integration_test):
        pass


class CalldUpWaitStrategy(WaitStrategy):
    def wait(self, integration_test):
        until.true(integration_test.calld_client.is_up, tries=5)


class CalldConnectionsOkWaitStrategy(WaitStrategy):
    def wait(self, integration_test):
        def is_ready():
            try:
                status = integration_test.calld.status()
            except requests.RequestException:
                status = {}
            assert_that(
                status,
                has_entries(
                    {
                        'ari': has_entry('status', 'ok'),
                        'bus_consumer': has_entry('status', 'ok'),
                    }
                ),
            )

        until.assert_(is_ready, tries=10)


class CalldEverythingOkWaitStrategy(WaitStrategy):
    def wait(self, integration_test):
        def is_ready():
            try:
                status = integration_test.calld.status()
            except requests.RequestException:
                status = {}
            assert_that(
                status,
                has_entries(
                    {
                        'ari': has_entry('status', 'ok'),
                        'bus_consumer': has_entry('status', 'ok'),
                        'service_token': has_entry('status', 'ok'),
                    }
                ),
            )

        until.assert_(is_ready, tries=60)
