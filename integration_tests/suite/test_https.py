# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import time

from hamcrest import assert_that
from hamcrest import contains_string
from .base import IntegrationTest


class TestHTTPSMissingCertificate(IntegrationTest):
    asset = 'no_ssl_certificate'

    def test_given_inexisting_SSL_certificate_when_ctid_ng_starts_then_ctid_ng_stops(self):
        for _ in range(10):
            status = self.service_status()
            if not status['State']['Running']:
                break
            time.sleep(1)
        else:
            self.fail('xivo-ctid-ng did not stop while missing SSL certificate')

        log = self.service_logs()
        assert_that(log, contains_string("No such file or directory: '/usr/share/xivo-certs/server.crt'"))


class TestHTTPSMissingPrivateKey(IntegrationTest):
    asset = 'no_ssl_private_key'

    def test_given_inexisting_SSL_private_key_when_ctid_ng_starts_then_ctid_ng_stops(self):
        for _ in range(10):
            status = self.service_status()
            if not status['State']['Running']:
                break
            time.sleep(1)
        else:
            self.fail('xivo-ctid-ng did not stop while missing SSL private key')

        log = self.service_logs()
        assert_that(log, contains_string("No such file or directory: '/usr/share/xivo-certs/server.key'"))
