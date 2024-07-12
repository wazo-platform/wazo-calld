# Copyright 2016-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests
from hamcrest import assert_that, empty, has_entries, has_entry, not_
from wazo_test_helpers import until
from wazo_test_helpers.wait_strategy import (
    ComponentsWaitStrategy,
    NoWaitStrategy,
    WaitStrategy,
)

__all__ = [
    'NoWaitStrategy',
]


class CalldComponentsWaitStrategy(ComponentsWaitStrategy):
    def get_status(self, integration_test):
        return integration_test.calld.status()


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

        until.assert_(is_ready, timeout=60)


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
                        'plugins': not_(empty()),
                    }
                ),
            )
            for plugin in status['plugins'].values():
                assert_that(plugin, has_entries({'status': 'ok'}))

        until.assert_(is_ready, timeout=60)


class AsteriskReadyWaitStrategy(WaitStrategy):
    def wait(self, integration_test):
        def is_ready():
            result = integration_test.docker_exec(
                ['asterisk', '-rx', 'core waitfullybooted'], service_name='ari'
            )
            assert result == b'Asterisk has fully booted.\n'

        until.assert_(is_ready, timeout=60)


class AmidReadyWaitStrategy(WaitStrategy):
    def wait(self, integration_test):
        def is_ready():
            try:
                status = integration_test.amid.status()
            except requests.RequestException:
                status = {}
            assert_that(
                status,
                has_entries(
                    {
                        'ami_socket': has_entry('status', 'ok'),
                        'bus_publisher': has_entry('status', 'ok'),
                        'rest_api': has_entry('status', 'ok'),
                        'service_token': has_entry('status', 'ok'),
                    }
                ),
            )

        until.assert_(is_ready, timeout=60)


class _ServicesWaitStrategy(WaitStrategy):
    _strategies: dict[str, WaitStrategy] = {
        'amid': AmidReadyWaitStrategy(),
        'asterisk': AsteriskReadyWaitStrategy(),
        'calld': CalldEverythingOkWaitStrategy(),
    }

    def __init__(self, services=None):
        self._services = self._strategies.keys() if services is None else services

    def wait(self, integration_test):
        for service in self._services:
            self._strategies[service].wait(integration_test)


class CalldAndAsteriskAndAmidWaitStrategy(_ServicesWaitStrategy):
    def __init__(self):
        super().__init__(services=['calld', 'asterisk', 'amid'])


class CalldAndAsteriskWaitStrategy(_ServicesWaitStrategy):
    def __init__(self):
        super().__init__(services=['calld', 'asterisk'])
