# Copyright 2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests

from .helpers.base import IntegrationTest
from .helpers.constants import CALLD_SERVICE_TOKEN
from .helpers.wait_strategy import CalldComponentsWaitStrategy


class TestHttpInterface(IntegrationTest):
    asset = 'basic_rest'
    wait_strategy = CalldComponentsWaitStrategy(['service_token'])

    def test_that_empty_body_returns_400(self):
        base_url = f'http://127.0.0.1:{self.service_port(9500, "calld")}'
        headers = {
            'X-Auth-Token': CALLD_SERVICE_TOKEN,
        }

        url = f'{base_url}/1.0/applications/00000000-0000-0000-0000-000000000000/calls'
        response = requests.post(url, data='', headers=headers)
        assert response.status_code == 400

        response = requests.post(url, data=None, headers=headers)
        assert response.status_code == 400

        url = f'{base_url}/1.0/config'
        response = requests.patch(url, data='', headers=headers)
        assert response.status_code == 400

        response = requests.patch(url, data=None, headers=headers)
        assert response.status_code == 400
