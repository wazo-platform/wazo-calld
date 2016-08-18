# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import requests
import pprint

from hamcrest import assert_that, empty

from .test_api.base import IntegrationTest
from .test_api.wait_strategy import NoWaitStrategy


class TestDocumentation(IntegrationTest):

    asset = 'documentation'
    wait_strategy = NoWaitStrategy()

    def test_documentation_errors(self):
        api_url = 'https://ctid-ng:9500/1.0/api/api.json'
        self.validate_api(api_url)

    def validate_api(self, url):
        validator_url = u'http://localhost:18080/debug'
        response = requests.get(validator_url, params={'url': url})
        assert_that(response.json(), empty(), pprint.pformat(response.json()))
