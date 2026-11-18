# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests
from hamcrest import assert_that, contains_string, equal_to

from .helpers.base import IntegrationTest
from .helpers.wait_strategy import CalldUpWaitStrategy


class TestMetrics(IntegrationTest):
    asset = 'basic_rest'
    wait_strategy = CalldUpWaitStrategy()

    def _url(self, path):
        return f'http://127.0.0.1:{self.service_port(9500, "calld")}/1.0/{path}'

    def test_metrics_without_token(self):
        self.calld.status()

        response = requests.get(self._url('metrics'))

        assert_that(response.status_code, equal_to(200))
        assert_that(
            response.text,
            contains_string('flask_http_request_total{method="GET",status="200"}'),
        )
        assert_that(
            response.text,
            contains_string(
                'flask_http_request_duration_seconds_count'
                '{endpoint="statusresource",method="GET",status="200"}'
            ),
        )
