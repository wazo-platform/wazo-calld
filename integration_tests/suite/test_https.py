# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that
from hamcrest import contains_string
from xivo_test_helpers import until

from .helpers.base import IntegrationTest
from .helpers.wait_strategy import NoWaitStrategy


class TestHTTPSMissingCertificate(IntegrationTest):
    asset = 'no_ssl_certificate'
    wait_strategy = NoWaitStrategy()

    def test_given_no_ssl_certificate_when_calld_starts_then_calld_stops(self):
        def calld_is_stopped():
            status = self.service_status()
            return not status['State']['Running']

        until.true(calld_is_stopped, tries=10, message='wazo-calld did not stop while missing SSL certificate')

        log = self.service_logs()
        assert_that(log, contains_string("No such file or directory: '/usr/local/share/ssl/calld/invalid.crt'"))


class TestHTTPSMissingPrivateKey(IntegrationTest):
    asset = 'no_ssl_private_key'
    wait_strategy = NoWaitStrategy()

    def test_given_no_ssl_private_key_when_calld_starts_then_calld_stops(self):
        def calld_is_stopped():
            status = self.service_status()
            return not status['State']['Running']

        until.true(calld_is_stopped, tries=10, message='wazo-calld did not stop while missing SSL private key')

        log = self.service_logs()
        assert_that(log, contains_string("No such file or directory: '/usr/local/share/ssl/calld/invalid.key'"))
