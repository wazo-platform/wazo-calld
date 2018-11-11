# Copyright 2015-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import contains_string
from xivo_test_helpers import until

from .helpers.base import IntegrationTest
from .helpers.wait_strategy import NoWaitStrategy


class TestHTTPSMissingCertificate(IntegrationTest):
    asset = 'no_ssl_certificate'
    wait_strategy = NoWaitStrategy()

    def test_given_no_ssl_certificate_when_ctid_ng_starts_then_ctid_ng_stops(self):
        def ctid_ng_is_stopped():
            status = self.service_status()
            return not status['State']['Running']

        until.true(ctid_ng_is_stopped, tries=10, message='xivo-ctid-ng did not stop while missing SSL certificate')

        log = self.service_logs()
        assert_that(log, contains_string("No such file or directory: '/usr/local/share/ssl/ctid-ng/invalid.crt'"))


class TestHTTPSMissingPrivateKey(IntegrationTest):
    asset = 'no_ssl_private_key'
    wait_strategy = NoWaitStrategy()

    def test_given_no_ssl_private_key_when_ctid_ng_starts_then_ctid_ng_stops(self):
        def ctid_ng_is_stopped():
            status = self.service_status()
            return not status['State']['Running']

        until.true(ctid_ng_is_stopped, tries=10, message='xivo-ctid-ng did not stop while missing SSL private key')

        log = self.service_logs()
        assert_that(log, contains_string("No such file or directory: '/usr/local/share/ssl/ctid-ng/invalid.key'"))
