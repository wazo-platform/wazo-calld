# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock, call, patch
from unittest.mock import sentinel as s

from hamcrest import (
    assert_that,
    contains_exactly,
    contains_inanyorder,
    equal_to,
    has_entries,
    has_properties,
    not_,
)

from ..services import ConfdCache, Endpoint, EndpointsService, NotifyingStatusCache


class TestEndpointService(TestCase):
    def setUp(self):
        self.ari = Mock()
        self.ari.endpoints.list.return_value = []
        self.status_cache = NotifyingStatusCache(Mock(), self.ari)
        self.confd_cache = Mock(ConfdCache)

        self.service = EndpointsService(self.confd_cache, self.status_cache)

    def test_list_lines(self):
        self.confd_cache.list_lines.return_value = [
            {
                'id': 1,
                'technology': 'sip',
                'name': s.name_1,
                'tenant_uuid': s.tenant_uuid,
            },
            {
                'id': 2,
                'technology': 'iax',
                'name': s.name_2,
                'tenant_uuid': s.tenant_uuid,
            },
            {
                'id': 3,
                'technology': 'custom',
                'name': s.name_2,
                'tenant_uuid': s.tenant_uuid,
            },
        ]

        self.status_cache.add_endpoint(
            Endpoint('PJSIP', s.name_1, registered=True, channel_ids=[123, 456]),
        )

        items, filtered, total = self.service.list_lines(s.tenant_uuid)

        assert_that(filtered, equal_to(3))
        assert_that(total, equal_to(3))
        assert_that(
            items,
            contains_inanyorder(
                has_entries(id=1, registered=True, current_call_count=2),
                has_entries(id=2),
                has_entries(id=3),
            ),
        )

    def test_list_trunks(self):
        self.confd_cache.list_trunks.return_value = [
            {
                'id': 1,
                'technology': 'sip',
                'name': s.name_1,
                'tenant_uuid': s.tenant_uuid,
            },
            {
                'id': 2,
                'technology': 'iax',
                'name': s.name_2,
                'tenant_uuid': s.tenant_uuid,
            },
            {
                'id': 3,
                'technology': 'custom',
                'name': s.name_2,
                'tenant_uuid': s.tenant_uuid,
            },
        ]

        self.status_cache.add_endpoint(
            Endpoint('PJSIP', s.name_1, registered=True, channel_ids=[123, 456]),
        )

        items, filtered, total = self.service.list_trunks(s.tenant_uuid)

        assert_that(filtered, equal_to(3))
        assert_that(total, equal_to(3))
        assert_that(
            items,
            contains_inanyorder(
                has_entries(id=1, registered=True, current_call_count=2),
                has_entries(id=2),
                has_entries(id=3),
            ),
        )

    def _given_lines(self, *names):
        self.confd_cache.list_lines.return_value = [
            {'id': id_, 'technology': 'sip', 'name': name, 'tenant_uuid': s.tenant}
            for id_, name in enumerate(names, start=1)
        ]

    def test_list_lines_paginated(self):
        self._given_lines('c', 'a', 'd', 'b')

        items, total, filtered = self.service.list_lines(
            s.tenant, order='name', limit=2, offset=1
        )

        assert_that(
            items, contains_exactly(has_entries(name='b'), has_entries(name='c'))
        )
        assert_that(total, equal_to(4))
        assert_that(filtered, equal_to(4))

    def test_list_lines_offset_without_limit(self):
        self._given_lines('c', 'a', 'b')

        items, _, _ = self.service.list_lines(s.tenant, order='name', offset=1)

        assert_that(
            items, contains_exactly(has_entries(name='b'), has_entries(name='c'))
        )

    def test_list_lines_direction_desc(self):
        self._given_lines('a', 'c', 'b')

        items, _, _ = self.service.list_lines(s.tenant, order='id', direction='desc')

        assert_that(
            items,
            contains_exactly(has_entries(id=3), has_entries(id=2), has_entries(id=1)),
        )

    def test_list_lines_without_status_sorted_last_in_both_directions(self):
        self._given_lines('a', 'b', 'c')
        self.status_cache.add_endpoint(Endpoint('PJSIP', 'a', False, []))
        self.status_cache.add_endpoint(Endpoint('PJSIP', 'c', True, []))

        ascending, _, _ = self.service.list_lines(s.tenant, order='registered')
        descending, _, _ = self.service.list_lines(
            s.tenant, order='registered', direction='desc'
        )

        assert_that(
            ascending,
            contains_exactly(
                has_entries(name='a'), has_entries(name='c'), has_entries(name='b')
            ),
        )
        assert_that(
            descending,
            contains_exactly(
                has_entries(name='c'), has_entries(name='a'), has_entries(name='b')
            ),
        )

    def test_list_trunks_paginated(self):
        self.confd_cache.list_trunks.return_value = [
            {'id': 1, 'technology': 'sip', 'name': 'b', 'tenant_uuid': s.tenant},
            {'id': 2, 'technology': 'sip', 'name': 'a', 'tenant_uuid': s.tenant},
        ]

        items, total, filtered = self.service.list_trunks(
            s.tenant, order='name', limit=1
        )

        assert_that(items, contains_exactly(has_entries(name='a')))
        assert_that(total, equal_to(2))
        assert_that(filtered, equal_to(2))


class TestCachingConfdClient(TestCase):
    def setUp(self):
        self.confd = Mock()
        self.client = ConfdCache(self.confd)

    def test_add_line(self):
        self._set_cache([])

        self.client.add_line('sip', s.line_id, s.name, s.username, s.tenant_uuid)

        expected = {
            'id': s.line_id,
            'technology': 'sip',
            'name': s.name,
            'tenant_uuid': s.tenant_uuid,
        }

        result = self.client.get_line('sip', s.name)
        assert_that(result, equal_to(expected))

    def test_add_trunk(self):
        self._set_cache([])

        self.client.add_trunk('sip', s.trunk_id, s.name, s.username, s.tenant_uuid)

        expected = {
            'id': s.trunk_id,
            'technology': 'sip',
            'name': s.name,
            'tenant_uuid': s.tenant_uuid,
        }

        result = self.client.get_trunk('sip', s.name)
        assert_that(result, equal_to(expected))

        result = self.client.get_trunk_by_username('sip', s.username)
        assert_that(result, equal_to(expected))

    def test_delete_line(self):
        self._set_cache(
            lines=[
                {
                    'id': s.line_id,
                    'protocol': 'sip',
                    'name': s.name,
                    'endpoint_sip': {
                        'name': s.name,
                        'auth_section_options': [['username', s.username]],
                    },
                    'tenant_uuid': s.tenant_uuid,
                },
            ]
        )

        self.client.delete_line(s.line_id)

        result = self.client.get_line('sip', s.name)
        assert_that(result, equal_to(None))

    def test_delete_trunk(self):
        self._set_cache(
            trunks=[
                {
                    'id': s.trunk_id,
                    'endpoint_sip': {
                        'name': s.name,
                        'registration_section_options': [['client_uri', s.username]],
                    },
                    'tenant_uuid': s.tenant_uuid,
                },
            ]
        )

        self.client.delete_trunk(s.trunk_id)

        result = self.client.get_trunk('sip', s.name)
        assert_that(result, equal_to(None))

        result = self.client.get_trunk_by_username('sip', s.username)
        assert_that(result, equal_to(None))

    def test_update_line(self):
        self._set_cache(
            lines=[
                {
                    'id': s.line_id,
                    'protocol': 'sip',
                    'name': s.name,
                    'endpoint_sip': {
                        'name': s.name,
                        'auth_section_options': [['username', s.username]],
                    },
                    'tenant_uuid': s.tenant_uuid,
                },
            ]
        )

        self.client.update_line(
            'sip', s.line_id, s.new_name, s.new_username, s.tenant_uuid
        )

        result = self.client.get_line('sip', s.new_name)
        assert_that(
            result,
            has_entries(
                id=s.line_id,
                technology='sip',
                name=s.new_name,
                tenant_uuid=s.tenant_uuid,
            ),
        )

        result = self.client.get_line('sip', s.name)
        assert_that(result, equal_to(None))

    def test_update_trunk(self):
        self._set_cache(
            trunks=[
                {
                    'id': s.trunk_id,
                    'endpoint_sip': {
                        'name': s.name,
                        'registration_section_options': [['client_uri', s.username]],
                    },
                    'tenant_uuid': s.tenant_uuid,
                },
            ]
        )

        self.client.update_trunk(
            'sip', s.trunk_id, s.new_name, s.new_username, s.tenant_uuid
        )

        result = self.client.get_trunk('sip', s.new_name)
        assert_that(
            result,
            has_entries(
                id=s.trunk_id,
                technology='sip',
                name=s.new_name,
                tenant_uuid=s.tenant_uuid,
            ),
        )

        result = self.client.get_trunk('sip', s.name)
        assert_that(result, equal_to(None))

    def test_get_line(self):
        self._set_cache(
            lines=[
                {
                    'id': 1,
                    'name': s.name_1,
                    'protocol': 'sip',
                    'tenant_uuid': s.tenant_uuid_1,
                },
                {
                    'id': 2,
                    'name': s.name_2,
                    'protocol': 'sccp',
                    'tenant_uuid': s.tenant_uuid_2,
                },
            ]
        )

        result = self.client.get_line('PJSIP', s.name_1)
        assert_that(
            result,
            has_entries(
                id=1, name=s.name_1, technology='sip', tenant_uuid=s.tenant_uuid_1
            ),
        )

        result = self.client.get_line('SCCP', s.name_2)
        assert_that(
            result,
            has_entries(
                id=2, name=s.name_2, technology='sccp', tenant_uuid=s.tenant_uuid_2
            ),
        )

        result = self.client.get_line('PJSIP', s.name_2)
        assert_that(result, equal_to(None))

    def test_list_lines(self):
        self._set_cache(
            lines=[
                {
                    'id': 1,
                    'name': s.name_1,
                    'protocol': 'sip',
                    'tenant_uuid': s.tenant_uuid,
                },
                {
                    'id': 2,
                    'name': s.name_2,
                    'protocol': 'sccp',
                    'tenant_uuid': s.tenant_uuid,
                },
                {
                    'id': 3,
                    'name': s.interface,
                    'protocol': 'custom',
                    'tenant_uuid': s.tenant_uuid,
                },
                {
                    'id': 4,
                    'protocol': 'sip',
                    'name': 'ignored',
                    'tenant_uuid': s.other_tenant_uuid,
                },
            ]
        )

        result = self.client.list_lines(s.tenant_uuid)

        assert_that(
            result,
            contains_inanyorder(
                has_entries(id=1),
                has_entries(id=2),
                has_entries(id=3),
            ),
        )

    def test_list_trunks(self):
        self._set_cache(
            [
                {
                    'id': 1,
                    'endpoint_sip': {
                        'name': s.name_1,
                        'registration_section_options': [['client_uri', s.username_1]],
                    },
                    'tenant_uuid': s.tenant_uuid,
                },
                {
                    'id': 2,
                    'endpoint_iax': {'name': s.name},
                    'tenant_uuid': s.tenant_uuid,
                },
                {
                    'id': 3,
                    'endpoint_custom': {'interface': s.interface},
                    'tenant_uuid': s.tenant_uuid,
                },
                {
                    'id': 4,
                    'endpoint_sip': {
                        'name': s.ignored_name,
                        'registration_section_options': [
                            ['client_uri', s.ignored_username]
                        ],
                    },
                    'tenant_uuid': s.other_tenant_uuid,
                },
                {
                    'id': 5,
                    'endpoint_sip': None,
                    'endpoint_iax': None,
                    'endpoint_custom': None,
                    'tenant_uuid': s.tenant_uuid,
                },
            ]
        )

        result = self.client.list_trunks(s.tenant_uuid)

        assert_that(
            result,
            contains_inanyorder(
                has_entries(id=1),
                has_entries(id=2),
                has_entries(id=3),
            ),
        )

    def test_initialize_lines(self):
        self.confd.trunks.list.return_value = {'items': [], 'total': 0}
        self.confd.lines.list.return_value = {
            "total": 3,
            "items": [
                {
                    "id": 20,
                    "tenant_uuid": s.tenant_uuid,
                    "name": s.name_1,
                    "protocol": "sip",
                    "endpoint_sip": {
                        "id": 18,
                        "name": s.name_1,
                        'auth_section_options': [['username', '5h8osw24']],
                    },
                    "endpoint_sccp": None,
                    "endpoint_custom": None,
                },
                {
                    "id": 33,
                    "tenant_uuid": s.tenant_uuid,
                    "name": s.name_2,
                    "protocol": "sccp",
                    "endpoint_sip": None,
                    "endpoint_sccp": {"id": 5},
                    "endpoint_custom": None,
                },
                {
                    "id": 38,
                    "tenant_uuid": s.tenant_uuid,
                    "name": s.interface,
                    "protocol": "custom",
                    "endpoint_sip": None,
                    "endpoint_sccp": None,
                    "endpoint_custom": {"id": 3, "interface": s.interface},
                },
            ],
        }

        result = self.client.list_lines(s.tenant_uuid)

        assert_that(
            result,
            contains_inanyorder(
                has_entries(
                    id=20,
                    name=s.name_1,
                    technology='sip',
                    tenant_uuid=s.tenant_uuid,
                ),
                has_entries(
                    id=33,
                    name=s.name_2,
                    technology='sccp',
                    tenant_uuid=s.tenant_uuid,
                ),
                has_entries(
                    id=38,
                    name=s.interface,
                    technology='custom',
                    tenant_uuid=s.tenant_uuid,
                ),
            ),
        )

    @patch('wazo_calld.plugins.endpoints.services.CONFD_PAGE_SIZE', 2)
    def test_initialize_trunks_paginated(self):
        self.confd.trunks.list.side_effect = [
            {'items': [self._trunk(1), self._trunk(2)]},
            {'items': [self._trunk(3)]},
        ]
        self.confd.lines.list.return_value = {'items': [], 'total': 0}

        result = self.client.list_trunks(s.tenant_uuid)

        assert_that(
            result,
            contains_inanyorder(
                has_entries(id=1), has_entries(id=2), has_entries(id=3)
            ),
        )
        assert_that(
            self.confd.trunks.list.call_args_list,
            contains_exactly(
                call(recurse=True, limit=2, offset=0),
                call(recurse=True, limit=2, offset=2),
            ),
        )

    @patch('wazo_calld.plugins.endpoints.services.CONFD_PAGE_SIZE', 2)
    def test_initialize_lines_paginated(self):
        self.confd.trunks.list.return_value = {'items': [], 'total': 0}
        self.confd.lines.list.side_effect = [
            {'items': [self._line(1), self._line(2)]},
            {'items': [self._line(3)]},
        ]

        result = self.client.list_lines(s.tenant_uuid)

        assert_that(
            result,
            contains_inanyorder(
                has_entries(id=1), has_entries(id=2), has_entries(id=3)
            ),
        )
        assert_that(
            self.confd.lines.list.call_args_list,
            contains_exactly(
                call(recurse=True, limit=2, offset=0),
                call(recurse=True, limit=2, offset=2),
            ),
        )

    def _trunk(self, trunk_id):
        return {
            'id': trunk_id,
            'tenant_uuid': s.tenant_uuid,
            'endpoint_iax': {'name': f'trunk-{trunk_id}'},
        }

    def _line(self, line_id):
        return {
            'id': line_id,
            'tenant_uuid': s.tenant_uuid,
            'name': f'line-{line_id}',
            'protocol': 'sip',
        }

    def _set_cache(self, trunks=None, lines=None):
        if trunks:
            self.client._update_trunk_cache(trunks)
        if lines:
            self.client._update_line_cache(lines)

        self.client._initialized = True


class TestEndpoint(TestCase):
    def test_from_ari_endpoint_list_not_sip_registered(self):
        raw = {
            "technology": 'PJSIP',
            "resource": s.name,
            "state": "offline",
            "channel_ids": [],
        }

        result = Endpoint.from_ari_endpoint_list(raw)

        assert_that(
            result,
            has_properties(
                techno='PJSIP',
                name=s.name,
                registered=False,
                current_call_count=0,
            ),
        )

    def test_from_ari_endpoint_list_sip_registered(self):
        raw = {
            "technology": 'PJSIP',
            "resource": s.name,
            "state": "online",
            "channel_ids": [123455.43],
        }

        result = Endpoint.from_ari_endpoint_list(raw)

        assert_that(
            result,
            has_properties(
                techno='PJSIP',
                name=s.name,
                registered=True,
                current_call_count=1,
            ),
        )

    def test_from_ari_endpoint_list_iax2_with_calls(self):
        raw = {
            "technology": 'IAX2',
            "resource": s.name,
            "state": "unknown",
            "channel_ids": [123455.43, 124453.32],
        }

        result = Endpoint.from_ari_endpoint_list(raw)

        assert_that(
            result,
            has_properties(
                techno='IAX2',
                name=s.name,
                registered=None,
                current_call_count=2,
            ),
        )

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
        self.endpoint = Endpoint(
            s.techno, s.name, s.registered, [s.unique_id_1, s.unique_id_2]
        )
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
