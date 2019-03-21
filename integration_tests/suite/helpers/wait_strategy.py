# Copyright 2016-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import (
    assert_that,
    has_entries,
    has_entry,
)
from xivo_test_helpers import until


class WaitStrategy:

    def wait(self, integration_test):
        raise NotImplementedError()


class NoWaitStrategy(WaitStrategy):

    def wait(self, integration_test):
        pass


class CtidNgUpWaitStrategy(WaitStrategy):

    def wait(self, integration_test):
        until.true(integration_test.ctid_ng.is_up, tries=5)


class CtidNgConnectionsOkWaitStrategy(WaitStrategy):

    def wait(self, integration_test):

        def ctid_ng_is_ready():
            status = integration_test.ctid_ng.status()
            assert_that(status, has_entries({
                'ari': has_entry('status', 'ok'),
                'bus_consumer': has_entry('status', 'ok')
            }))

        until.assert_(ctid_ng_is_ready, tries=10)


class CtidNgEverythingOkWaitStrategy(WaitStrategy):

    def wait(self, integration_test):
        def ctid_ng_is_ready():
            status = integration_test.ctid_ng.status()
            assert_that(status, has_entries({
                'ari': has_entry('status', 'ok'),
                'bus_consumer': has_entry('status', 'ok'),
                'service_token': has_entry('status', 'ok'),
            }))

        until.assert_(ctid_ng_is_ready, tries=60)
