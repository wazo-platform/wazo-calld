# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase

from requests import HTTPError

from hamcrest import (
    assert_that,
    calling,
    contains,
    equal_to,
    has_entries,
    has_properties,
)
from unittest.mock import (
    Mock,
    sentinel as s,
)
from xivo_test_helpers.hamcrest.raises import raises

from wazo_calld.exceptions import WazoConfdError

from ..services import EndpointsService, Endpoint


class BaseEndpointsService(TestCase):
    def setUp(self):
        self.confd = Mock()
        self.ari = Mock()
        self.ari.endpoints.list.return_value = []
        self.service = EndpointsService(self.confd, self.ari)
        self.ari.endpoints.list.return_value = []


class TestListTrunks(BaseEndpointsService):
    def test_that_the_tenant_is_forwarded_to_confd(self):
        self.confd.trunks.list.return_value = {
            'total': s.total,
            'items': [],
        }

        self.service.list_trunks(s.tenant_uuid)

        self.confd.trunks.list.assert_called_once_with(tenant_uuid=s.tenant_uuid)

    def test_error_from_confd(self):
        self.confd.trunks.list.side_effect = HTTPError

        assert_that(
            calling(self.service.list_trunks).with_args(s.tenant_uuid),
            raises(WazoConfdError).matching(
                has_properties(
                    status_code=503,
                    id_='wazo-confd-error',
                )
            )
        )

    def test_total_field(self):
        self.confd.trunks.list.return_value = {
            'total': s.total,
            'items': [],
        }

        items, total, filtered = self.service.list_trunks(s.tenant_uuid)

        assert_that(total, equal_to(s.total))

    def test_filtered_field(self):
        self.confd.trunks.list.return_value = {
            'total': s.total,
            'items': [],
        }

        items, total, filtered = self.service.list_trunks(s.tenant_uuid)

        assert_that(filtered, equal_to(s.total))

    def test_sip_endpoints_registered(self):
        ast_endpoint = Endpoint('PJSIP', s.name, True, 2)
        self.service.status_cache.add_endpoint(ast_endpoint)
        self.confd.trunks.list.return_value = {
            'total': s.total,
            'items': [
                {
                    'id': s.id,
                    'endpoint_sip': {'name': s.name},
                    'endpoint_iax': None,
                    'endpoint_custom': None,
                }
            ]
        }

        items, total, filtered = self.service.list_trunks(s.tenant_uuid)

        assert_that(items, contains(has_entries(
            id=s.id,
            type='trunk',
            technology='sip',
            name=s.name,
            registered=True,
            current_call_count=2,
        )))

    def test_sip_endpoints_not_registered(self):
        ast_endpoint = Endpoint('PJSIP', s.name, False, 0)
        self.service.status_cache.add_endpoint(ast_endpoint)
        self.confd.trunks.list.return_value = {
            'total': s.total,
            'items': [
                {
                    'id': s.id,
                    'endpoint_sip': {'name': s.name},
                    'endpoint_iax': None,
                    'endpoint_custom': None,
                }
            ]
        }

        items, total, filtered = self.service.list_trunks(s.tenant_uuid)

        assert_that(items, contains(has_entries(
            id=s.id,
            type='trunk',
            technology='sip',
            name=s.name,
            registered=False,
            current_call_count=0,
        )))

    def test_sip_endpoints_before_asterisk_reload(self):
        self.confd.trunks.list.return_value = {
            'total': s.total,
            'items': [
                {
                    'id': s.id,
                    'endpoint_sip': {'name': s.name},
                    'endpoint_iax': None,
                    'endpoint_custom': None,
                }
            ]
        }
        self.ari.endpoints.list.return_value = []

        items, total, filtered = self.service.list_trunks(s.tenant_uuid)

        assert_that(items, contains(has_entries(
            id=s.id,
            type='trunk',
            technology='sip',
            name=s.name,
        )))

    def test_iax_endpoints(self):
        ast_endpoint = Endpoint('IAX2', s.name, None, 1)
        self.service.status_cache.add_endpoint(ast_endpoint)
        self.confd.trunks.list.return_value = {
            'total': s.total,
            'items': [
                {
                    'id': s.id,
                    'endpoint_sip': None,
                    'endpoint_iax': {'name': s.name},
                    'endpoint_custom': None,
                }
            ]
        }

        items, total, filtered = self.service.list_trunks(s.tenant_uuid)

        assert_that(items, contains(has_entries(
            id=s.id,
            type='trunk',
            technology='iax',
            name=s.name,
            current_call_count=1,
        )))

    def test_custom_endpoints(self):
        self.confd.trunks.list.return_value = {
            'total': s.total,
            'items': [
                {
                    'id': s.id,
                    'endpoint_sip': None,
                    'endpoint_iax': None,
                    'endpoint_custom': {'interface': s.interface},
                }
            ]
        }

        items, total, filtered = self.service.list_trunks(s.tenant_uuid)

        assert_that(items, contains(has_entries(
            id=s.id,
            type='trunk',
            technology='custom',
            name=s.interface,
        )))


class TestUpdateEndpoint(BaseEndpointsService):
    def test_updating_the_registered(self):
        ast_endpoint = Endpoint('PJSIP', s.name, False, 0)
        self.service.status_cache.add_endpoint(ast_endpoint)

        self.service.update_endpoint('PJSIP', s.name, registered=True)

        endpoint = self.service.status_cache.get('PJSIP', s.name)
        assert_that(endpoint, has_properties(
            techno='PJSIP',
            name=s.name,
            registered=True,
            current_call_count=0,
        ))

        self.service.update_endpoint('PJSIP', s.name, registered=False)

        endpoint = self.service.status_cache.get('PJSIP', s.name)
        assert_that(endpoint, has_properties(
            techno='PJSIP',
            name=s.name,
            registered=False,
            current_call_count=0,
        ))


class TestEndpoint(TestCase):
    def test_from_ari_endpoint_list_not_sip_registered(self):
        raw = {
            "technology": 'PJSIP',
            "resource": s.name,
            "state": "offline",
            "channel_ids": []
        }

        result = Endpoint.from_ari_endpoint_list(raw)

        assert_that(result, has_properties(
            techno='PJSIP',
            name=s.name,
            registered=False,
            current_call_count=0,
        ))

    def test_from_ari_endpoint_list_sip_registered(self):
        raw = {
            "technology": 'PJSIP',
            "resource": s.name,
            "state": "online",
            "channel_ids": [123455.43]
        }

        result = Endpoint.from_ari_endpoint_list(raw)

        assert_that(result, has_properties(
            techno='PJSIP',
            name=s.name,
            registered=True,
            current_call_count=1,
        ))

    def test_from_ari_endpoint_list_iax2_with_calls(self):
        raw = {
            "technology": 'IAX2',
            "resource": s.name,
            "state": "unknown",
            "channel_ids": [123455.43, 124453.32]
        }

        result = Endpoint.from_ari_endpoint_list(raw)

        assert_that(result, has_properties(
            techno='IAX2',
            name=s.name,
            registered=None,
            current_call_count=2,
        ))
