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
from mock import (
    Mock,
    sentinel as s,
)
from xivo_test_helpers.hamcrest.raises import raises

from wazo_calld.exceptions import WazoConfdError

from ..services import EndpointsService


class BaseEndpointsService(TestCase):
    def setUp(self):
        self.confd = Mock()
        self.service = EndpointsService(self.confd)


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

    def test_sip_endpoints(self):
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
        )))

    def test_iax_endpoints(self):
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
        )))

    def test_iax_custom(self):
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
