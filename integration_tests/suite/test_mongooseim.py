# -*- coding: utf-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests
from hamcrest import assert_that, equal_to

from .test_api.base import IntegrationTest
from .test_api.constants import VALID_TOKEN

CTID_NG_VERSION = '1.0'
BASE_URL = 'http://localhost:{port}/{version}'


class TestAuthenticationCoverage(IntegrationTest):

    asset = 'mongooseim'

    def test_auth_on_mongooseim_check_password(self):
        base_url = BASE_URL.format(port=self.service_port(9501, 'ctid-ng'), version=CTID_NG_VERSION)
        uri = '{}/mongooseim/authentication/check_password'.format(base_url)
        result = requests.get(uri, params={'pass': 'invalid-token', 'user': ''})
        assert_that(result.status_code, equal_to(401))

    def test_auth_on_mongooseim_check_password_with_non_matching_uuid(self):
        base_url = BASE_URL.format(port=self.service_port(9501, 'ctid-ng'), version=CTID_NG_VERSION)
        uri = '{}/mongooseim/authentication/check_password'.format(base_url)
        result = requests.get(uri, params={'pass': VALID_TOKEN, 'user': 'invalid-uuid'})
        assert_that(result.status_code, equal_to(401))
