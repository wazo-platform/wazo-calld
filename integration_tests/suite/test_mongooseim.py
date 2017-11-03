# -*- coding: utf-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests
from hamcrest import assert_that, equal_to

from .test_api.base import IntegrationTest
from .test_api.auth import MockUserToken

CTID_NG_VERSION = '1.0'
BASE_URL = 'http://localhost:{port}/{version}'


class TestAuthenticationCoverage(IntegrationTest):

    asset = 'mongooseim'

    def setUp(self):
        super(TestAuthenticationCoverage, self).setUp()
        base_url = BASE_URL.format(port=self.service_port(9501, 'ctid-ng'), version=CTID_NG_VERSION)
        self.url = '{}/mongooseim/authentication/check_password'.format(base_url)

    def test_auth_on_mongooseim_check_password(self):
        result = requests.get(self.url, params={'pass': 'invalid-token', 'user': ''})
        assert_that(result.status_code, equal_to(401))

    def test_auth_on_mongooseim_check_password_with_non_matching_uuid(self):
        self.auth.set_token(MockUserToken('my-token', 'user-uuid', ['websocketd']))
        result = requests.get(self.url, params={'pass': 'my-token', 'user': 'invalid-uuid'})
        assert_that(result.status_code, equal_to(401))

    def test_auth_on_mongooseim_check_password_with_matching_uuid(self):
        self.auth.set_token(MockUserToken('my-token', 'user-uuid', ['websocketd']))
        result = requests.get(self.url, params={'pass': 'my-token', 'user': 'user-uuid'})
        assert_that(result.text, equal_to('true'))
        assert_that(result.status_code, equal_to(200))

    def test_auth_on_mongooseim_check_password_with_admin_acl(self):
        self.auth.set_token(MockUserToken('my-token', 'user-uuid', ['mongooseim.admin']))
        result = requests.get(self.url, params={'pass': 'my-token', 'user': 'user-uuid'})
        assert_that(result.text, equal_to('true'))
        assert_that(result.status_code, equal_to(200))
