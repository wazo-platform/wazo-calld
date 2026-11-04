# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
from unittest import TestCase
from unittest.mock import Mock, patch

from flask import Flask
from flask_restful import Api
from hamcrest import assert_that, contains_exactly, equal_to, has_entries
from requests import ConnectTimeout, HTTPError

from wazo_calld.http import ErrorCatchingResource

from ..http import LineEndpoints, TrunkEndpoints
from ..services import (
    CONFD_LIST_CONCURRENCY,
    Endpoint,
    EndpointsService,
    NotifyingStatusCache,
)

TENANT = '00000000-0000-4000-8000-000000000001'


class _Lines(LineEndpoints):
    method_decorators = ErrorCatchingResource.method_decorators


class _Trunks(TrunkEndpoints):
    method_decorators = ErrorCatchingResource.method_decorators


class TestEndpointsHTTP(TestCase):
    def setUp(self):
        self.confd = Mock(host='confd', port=9486, timeout=10)
        self.confd.lines.list.return_value = {
            'total': 12,
            'items': [
                {'id': 1, 'protocol': 'sip', 'name': 'line-a', 'tenant_uuid': TENANT}
            ],
        }
        self.confd.trunks.list.return_value = {
            'total': 1,
            'items': [
                {
                    'id': 4,
                    'tenant_uuid': TENANT,
                    'endpoint_sip': None,
                    'endpoint_iax': None,
                    'endpoint_custom': None,
                }
            ],
        }
        ari = Mock()
        status_cache = NotifyingStatusCache(Mock(), ari)
        status_cache.add_endpoint(Endpoint('PJSIP', 'line-a', True, ['c1']))
        service = EndpointsService(self.confd, status_cache)

        app = Flask(__name__)
        api = Api(app)
        api.add_resource(_Lines, '/lines', resource_class_args=[service])
        api.add_resource(_Trunks, '/trunks', resource_class_args=[service])
        self.client = app.test_client()
        tenant = patch('wazo_calld.plugins.endpoints.http.Tenant')
        tenant.start().autodetect.return_value = Mock(uuid=TENANT)
        self.addCleanup(tenant.stop)

    def test_lines_without_parameters_list_the_whole_tenant(self):
        response = self.client.get('/lines')

        assert_that(response.status_code, equal_to(200))
        assert_that(
            response.json,
            equal_to(
                {
                    'items': [
                        {
                            'id': 1,
                            'technology': 'sip',
                            'name': 'line-a',
                            'registered': True,
                            'current_call_count': 1,
                        }
                    ],
                    'total': 12,
                    'filtered': 12,
                }
            ),
        )
        self.confd.lines.list.assert_called_once_with(tenant_uuid=TENANT)

    def test_list_parameters_reach_confd(self):
        response = self.client.get(
            '/lines?limit=2&offset=0&order=name&direction=desc&search=a&other=1'
        )

        assert_that(response.status_code, equal_to(200))
        self.confd.lines.list.assert_called_once_with(
            tenant_uuid=TENANT,
            limit=2,
            offset=0,
            order='name',
            direction='desc',
            search='a',
        )

    def test_a_trunk_without_endpoint_is_listed_as_unknown(self):
        response = self.client.get('/trunks?search=x')

        assert_that(response.status_code, equal_to(200))
        assert_that(
            response.json,
            has_entries(
                items=contains_exactly(
                    {
                        'id': 4,
                        'technology': 'unknown',
                        'name': None,
                        'registered': None,
                        'current_call_count': None,
                    }
                ),
                total=1,
                filtered=1,
            ),
        )
        self.confd.trunks.list.assert_called_once_with(tenant_uuid=TENANT, search='x')

    def test_invalid_parameters_are_refused_before_confd(self):
        for query in (
            'limit=0',
            'limit=-1',
            'limit=x',
            'offset=-1',
            'direction=up',
        ):
            for path in ('/lines', '/trunks'):
                response = self.client.get(f'{path}?{query}')
                assert_that(response.status_code, equal_to(400), f'{path}?{query}')

        self.confd.lines.list.assert_not_called()
        self.confd.trunks.list.assert_not_called()

    def test_a_confd_400_is_answered_400_with_its_message(self):
        confd_response = Mock(status_code=400)
        confd_response.json.return_value = [
            "Input Error - field 'order': Must be one of: id."
        ]
        self.confd.trunks.list.side_effect = HTTPError(response=confd_response)

        response = self.client.get('/trunks?order=nope')

        assert_that(response.status_code, equal_to(400))
        assert_that(
            response.json,
            has_entries(
                error_id='invalid-list-parameters',
                message="Input Error - field 'order': Must be one of: id.",
            ),
        )

    def test_a_confd_timeout_is_503_confd_unreachable(self):
        self.confd.lines.list.side_effect = ConnectTimeout()

        response = self.client.get('/lines')

        assert_that(response.status_code, equal_to(503))
        assert_that(response.json, has_entries(error_id='wazo-confd-unreachable'))

    def test_a_list_beyond_the_cap_is_503_confd_busy(self):
        release = threading.Event()
        entered = threading.Semaphore(0)

        def slow_list(**kwargs):
            entered.release()
            release.wait(5)
            return {'total': 0, 'items': []}

        self.confd.lines.list.side_effect = slow_list
        threads = [
            threading.Thread(target=self.client.get, args=('/lines',))
            for _ in range(CONFD_LIST_CONCURRENCY)
        ]
        for thread in threads:
            thread.start()
        for _ in threads:
            assert entered.acquire(timeout=5)
        try:
            response = self.client.get('/trunks')
        finally:
            release.set()
            for thread in threads:
                thread.join(5)

        assert_that(response.status_code, equal_to(503))
        assert_that(
            response.json,
            has_entries(
                error_id='wazo-calld-confd-busy',
                message='too many concurrent requests to wazo-confd, retry later',
            ),
        )
        self.confd.trunks.list.assert_not_called()
