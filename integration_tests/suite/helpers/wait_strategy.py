# Copyright 2016-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import (
    assert_that,
    has_entries,
    has_entry,
)
import psycopg2
import time
from xivo_test_helpers import until

from .constants import MONGOOSEIM_ODBC_START_INTERVAL
from .constants import DB_URI


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


class CtidNgMongooseImEverythingOkWaitStrategy(WaitStrategy):

    def wait(self, integration_test):
        self._wait_for_ctid_ng(integration_test)
        self._wait_for_mongooseim(integration_test)

    def _wait_for_ctid_ng(self, integration_test):
        CtidNgEverythingOkWaitStrategy().wait(integration_test)

    def _wait_for_mongooseim(self, integration_test):
        until.true(self._mongooseim_db_is_ready, integration_test, timeout=10, interval=0.25)

    def _mongooseim_db_is_ready(self, integration_test):
        try:
            uri = DB_URI.format(PORT=integration_test.service_port(5432, 'postgres'))
            psycopg2.connect(uri)
            self._wait_mongooseim_interval()
            return True
        except psycopg2.OperationalError as e:
            pass
        return False

    def _wait_mongooseim_interval(self):
        time.sleep(MONGOOSEIM_ODBC_START_INTERVAL)
