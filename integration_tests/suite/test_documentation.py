# Copyright 2016-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import requests
import yaml

from openapi_spec_validator import validate_v2_spec

from .helpers.base import IntegrationTest
from .helpers.wait_strategy import NoWaitStrategy

logger = logging.getLogger('openapi_spec_validator')
logger.setLevel(logging.INFO)


class TestDocumentation(IntegrationTest):

    asset = 'documentation'
    wait_strategy = NoWaitStrategy()

    def test_documentation_errors(self):
        port = self.service_port(9500, 'calld')
        api_url = 'https://localhost:{port}/1.0/api/api.yml'.format(port=port)
        api = requests.get(api_url, verify=False)
        validate_v2_spec(yaml.safe_load(api.text))
