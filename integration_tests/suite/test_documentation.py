# -*- coding: utf-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests
import pprint

from hamcrest import assert_that, empty

from .helpers.base import IntegrationTest
from .helpers.wait_strategy import NoWaitStrategy


class TestDocumentation(IntegrationTest):

    asset = 'documentation'
    wait_strategy = NoWaitStrategy()

    def test_documentation_errors(self):
        ctid_ng_port = self.service_port(9500, 'ctid-ng')
        api_url = 'https://localhost:{port}/1.0/api/api.yml'.format(port=ctid_ng_port)
        api = requests.get(api_url, verify=False)
        self.validate_api(api)

    def validate_api(self, api):
        validator_port = self.service_port(8080, 'swagger-validator')
        validator_url = 'http://localhost:{port}/debug'.format(port=validator_port)
        response = requests.post(validator_url, data=api)
        assert_that(response.json(), empty(), pprint.pformat(response.json()))
