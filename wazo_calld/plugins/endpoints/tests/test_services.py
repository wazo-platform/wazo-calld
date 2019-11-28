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
    not_,
)
from unittest.mock import (
    Mock,
    patch,
    sentinel as s,
)
from xivo_test_helpers.hamcrest.raises import raises

from wazo_calld.exceptions import WazoConfdError

from ..services import EndpointsService, Endpoint, NotifyingStatusCache


class BaseEndpointsService(TestCase):
    def setUp(self):
        self.confd = Mock()
        self.ari = Mock()
        self.ari.endpoints.list.return_value = []
        self.publisher = Mock()
        self.service = EndpointsService(self.confd, self.ari, self.publisher)
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
        call_ids = ['1234567.8', '456687.8']
        ast_endpoint = Endpoint('PJSIP', s.name, True, call_ids)
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
        ast_endpoint = Endpoint('PJSIP', s.name, False, [])
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
        call_ids = ['1234556.7']
        ast_endpoint = Endpoint('IAX2', s.name, None, call_ids)
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


class TestUpdateLineEndpoint(BaseEndpointsService):
    def test_updating_the_registered(self):
        ast_endpoint = Endpoint('PJSIP', s.name, False, [])
        self.service.status_cache.add_endpoint(ast_endpoint)

        self.confd.trunks.list.return_value = {'items': []}
        self.service.update_line_endpoint('PJSIP', s.name, registered=True)

        endpoint = self.service.status_cache.get('PJSIP', s.name)
        assert_that(endpoint, has_properties(
            techno='PJSIP',
            name=s.name,
            registered=True,
            current_call_count=0,
        ))

        self.service.update_line_endpoint('PJSIP', s.name, registered=False)

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

    def test_add_call(self):
        endpoint = Endpoint(s.techno, s.name, True, [])

        endpoint.add_call(s.unique_id_1)
        assert_that(endpoint.current_call_count, equal_to(1))

        endpoint.add_call(s.unique_id_1)
        assert_that(endpoint.current_call_count, equal_to(1))

        endpoint.add_call(s.unique_id_2)
        assert_that(endpoint.current_call_count, equal_to(2))

    def test_remove_call(self):
        endpoint = Endpoint(s.techno, s.name, True, [s.unique_id_1, s.unique_id_2])

        endpoint.remove_call(s.unique_id_1)
        assert_that(endpoint.current_call_count, equal_to(1))

        endpoint.remove_call(s.unique_id_1)
        assert_that(endpoint.current_call_count, equal_to(1))

        endpoint.remove_call(s.unique_id_2)
        assert_that(endpoint.current_call_count, equal_to(0))

    def test_eq(self):
        assert_that(
            Endpoint(s.techno, s.name, True, []),
            equal_to(Endpoint(s.techno, s.name, True, [])),
        )

        assert_that(
            Endpoint(s.techno, s.name, True, []),
            not_(equal_to(Endpoint(s.techno, s.name, False, []))),
        )

        # The interface for the state of an endpoint is currently the number of calls
        assert_that(
            Endpoint(s.techno, s.name, True, [s.unique_id_1]),
            equal_to(Endpoint(s.techno, s.name, True, [s.unique_id_2])),
        )


class TestNotifyingStatusCache(TestCase):

    def setUp(self):
        self.ari = Mock()
        self.notify = Mock()
        self.endpoint = Endpoint(s.techno, s.name, s.registered, [s.unique_id_1, s.unique_id_2])
        self.cache = NotifyingStatusCache(
            self.notify,
            self.ari,
            endpoints={s.techno: {s.name: self.endpoint}},
        )

    def test_no_change(self):
        with self.cache.update(s.techno, s.name) as e:
            e.add_call(s.unique_id_1)  # Already there
            e.registered = s.registered  # Already registered
            e.remove_call(s.unique_id_3)  # Not there

        self.notify.assert_not_called()

    def test_register_change(self):
        with self.cache.update(s.techno, s.name) as e:
            e.registered = True

        self.notify.assert_called_once_with(e)

    def test_call_count_change(self):
        with self.cache.update(s.techno, s.name) as e:
            e.remove_call(s.unique_id_2)

        self.notify.assert_called_once_with(e)

    def test_not_found_does_not_raise(self):
        with self.cache.update(s.not_found, s.name) as e:
            assert_that(e, equal_to(None))
            e.add_call(s.unique_id_1)
