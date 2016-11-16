# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import has_entries
from xivo_test_helpers import until


class WaitStrategy(object):

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
            assert_that(status['connections'], has_entries({'ari': 'ok',
                                                            'bus_consumer': 'ok'}))
        until.assert_(ctid_ng_is_ready, tries=30)
