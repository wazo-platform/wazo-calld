# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import sentinel as s

from hamcrest import (
    assert_that,
    calling,
    contains_exactly,
    equal_to,
    has_entries,
    has_properties,
    not_,
    raises,
)
from requests import HTTPError, ReadTimeout

from wazo_calld.plugin_helpers.exceptions import WazoConfdUnreachable

from ..exceptions import ConfdBusy, InvalidListParameters
from ..services import (
    CONFD_LIST_CONCURRENCY,
    Endpoint,
    EndpointsService,
    NotifyingStatusCache,
)

CONFD_LINES = [
    {
        'id': 1,
        'protocol': 'sip',
        'name': 'line-a',
        'tenant_uuid': s.tenant_uuid,
        'endpoint_sip': {'name': 'line-a'},
    },
    {'id': 2, 'protocol': 'sccp', 'name': '1001', 'tenant_uuid': s.tenant_uuid},
    {'id': 3, 'protocol': 'custom', 'name': 'dahdi/i1/1', 'tenant_uuid': s.tenant_uuid},
]

CONFD_TRUNKS = [
    {'id': 1, 'tenant_uuid': s.tenant_uuid, 'endpoint_sip': {'name': 'trunk-a'}},
    {'id': 2, 'tenant_uuid': s.tenant_uuid, 'endpoint_iax': {'name': 'iax-a'}},
    {
        'id': 3,
        'tenant_uuid': s.tenant_uuid,
        'endpoint_custom': {'interface': 'dahdi/g1'},
    },
    {
        'id': 4,
        'tenant_uuid': s.tenant_uuid,
        'endpoint_sip': None,
        'endpoint_iax': None,
        'endpoint_custom': None,
    },
]


def http_error(status, body=None):
    response = Mock(status_code=status)
    response.json.return_value = body
    return HTTPError(response=response)


class TestEndpointService(TestCase):
    def setUp(self):
        self.ari = Mock()
        self.ari.endpoints.list.return_value = []
        self.status_cache = NotifyingStatusCache(Mock(), self.ari)
        self.confd = Mock()
        self.confd.lines.list.return_value = {'total': 30, 'items': CONFD_LINES}
        self.confd.trunks.list.return_value = {'total': 40, 'items': CONFD_TRUNKS}

        self.service = EndpointsService(self.confd, self.status_cache)

    def test_list_lines_reads_one_page_of_the_tenant(self):
        self.status_cache.add_endpoint(
            Endpoint('PJSIP', 'line-a', registered=True, channel_ids=[123, 456]),
        )

        items, total, filtered = self.service.list_lines(s.tenant_uuid)

        self.confd.lines.list.assert_called_once_with(tenant_uuid=s.tenant_uuid)
        assert_that(total, equal_to(30))
        assert_that(filtered, equal_to(30))
        assert_that(
            items,
            contains_exactly(
                equal_to(
                    {
                        'id': 1,
                        'technology': 'sip',
                        'name': 'line-a',
                        'tenant_uuid': s.tenant_uuid,
                        'registered': True,
                        'current_call_count': 2,
                    }
                ),
                equal_to(
                    {
                        'id': 2,
                        'technology': 'sccp',
                        'name': '1001',
                        'tenant_uuid': s.tenant_uuid,
                    }
                ),
                has_entries(id=3, technology='custom', name='dahdi/i1/1'),
            ),
        )

    def test_list_trunks_reads_one_page_of_the_tenant(self):
        self.status_cache.add_endpoint(
            Endpoint('PJSIP', 'trunk-a', registered=True, channel_ids=[1]),
        )
        self.status_cache.add_endpoint(
            Endpoint('IAX2', 'iax-a', registered=None, channel_ids=[1, 2, 3]),
        )

        items, total, filtered = self.service.list_trunks(s.tenant_uuid)

        self.confd.trunks.list.assert_called_once_with(tenant_uuid=s.tenant_uuid)
        assert_that(total, equal_to(40))
        assert_that(filtered, equal_to(40))
        assert_that(
            items,
            contains_exactly(
                has_entries(
                    id=1,
                    technology='sip',
                    name='trunk-a',
                    registered=True,
                    current_call_count=1,
                ),
                has_entries(
                    id=2,
                    technology='iax',
                    name='iax-a',
                    registered=None,
                    current_call_count=3,
                ),
                has_entries(id=3, technology='custom', name='dahdi/g1'),
                equal_to({'id': 4, 'name': None, 'tenant_uuid': s.tenant_uuid}),
            ),
        )

    def test_a_list_without_total_is_counted_as_returned(self):
        self.confd.lines.list.return_value = {'items': CONFD_LINES}

        _, total, filtered = self.service.list_lines(s.tenant_uuid)

        assert_that((total, filtered), equal_to((3, 3)))

    def test_list_parameters_are_passed_to_confd_as_given(self):
        params = {
            'limit': 2,
            'offset': 4,
            'order': 'name',
            'direction': 'desc',
            'search': 'abc',
        }

        self.service.list_lines(s.tenant_uuid, **params)
        self.service.list_trunks(s.tenant_uuid, **params)

        self.confd.lines.list.assert_called_once_with(
            tenant_uuid=s.tenant_uuid, **params
        )
        self.confd.trunks.list.assert_called_once_with(
            tenant_uuid=s.tenant_uuid, **params
        )

    def test_a_confd_400_is_invalid_list_parameters(self):
        self.confd.lines.list.side_effect = http_error(
            400, ["Input Error - field 'order': Must be one of: name."]
        )

        assert_that(
            calling(self.service.list_lines).with_args(s.tenant_uuid, order='x'),
            raises(InvalidListParameters),
        )
        try:
            self.service.list_lines(s.tenant_uuid, order='x')
        except InvalidListParameters as e:
            assert_that(
                e,
                has_properties(
                    status_code=400,
                    message="Input Error - field 'order': Must be one of: name.",
                ),
            )

    def test_a_confd_timeout_is_confd_unreachable(self):
        self.confd.trunks.list.side_effect = ReadTimeout()

        assert_that(
            calling(self.service.list_trunks).with_args(s.tenant_uuid),
            raises(WazoConfdUnreachable),
        )

    def test_another_confd_error_is_not_hidden(self):
        self.confd.lines.list.side_effect = http_error(500, {'message': 'boom'})

        assert_that(
            calling(self.service.list_lines).with_args(s.tenant_uuid),
            raises(HTTPError),
        )
        assert_that(
            calling(self.service.list_lines).with_args(s.tenant_uuid),
            not_(raises(WazoConfdUnreachable)),
        )


class TestConfdConcurrencyCap(TestCase):
    def setUp(self):
        self.confd = Mock()
        self.release = threading.Event()
        self.entered = threading.Semaphore(0)
        self.service = EndpointsService(
            self.confd, NotifyingStatusCache(Mock(), Mock())
        )

    def _slow_list(self, **kwargs):
        self.entered.release()
        self.release.wait(5)
        return {'total': 0, 'items': []}

    def _hold(self, count):
        self.confd.lines.list.side_effect = self._slow_list
        self.confd.trunks.list.side_effect = self._slow_list
        threads = [
            threading.Thread(
                target=self.service.list_lines
                if index % 2
                else self.service.list_trunks,
                args=(s.tenant_uuid,),
            )
            for index in range(count)
        ]
        for thread in threads:
            thread.start()
        for _ in range(count):
            assert self.entered.acquire(timeout=5)
        return threads

    def _release(self, threads):
        self.release.set()
        for thread in threads:
            thread.join(5)

    def test_the_cap_is_four(self):
        assert_that(CONFD_LIST_CONCURRENCY, equal_to(4))

    def test_a_list_beyond_the_cap_is_refused_without_calling_confd(self):
        threads = self._hold(CONFD_LIST_CONCURRENCY)
        try:
            assert_that(
                calling(self.service.list_lines).with_args(s.tenant_uuid),
                raises(ConfdBusy),
            )
            assert_that(
                calling(self.service.list_trunks).with_args(s.tenant_uuid),
                raises(ConfdBusy),
            )
            calls = self.confd.lines.list.call_count + self.confd.trunks.list.call_count
            assert_that(calls, equal_to(CONFD_LIST_CONCURRENCY))
        finally:
            self._release(threads)

        items, _, _ = self.service.list_lines(s.tenant_uuid)

        assert_that(items, equal_to([]))

    def test_below_the_cap_a_list_passes(self):
        threads = self._hold(CONFD_LIST_CONCURRENCY - 1)
        try:
            self.release.set()
            items, _, _ = self.service.list_trunks(s.tenant_uuid)
        finally:
            self._release(threads)

        assert_that(items, equal_to([]))

    def test_a_failed_list_releases_its_slot(self):
        self.confd.lines.list.side_effect = ReadTimeout()
        for _ in range(CONFD_LIST_CONCURRENCY + 1):
            assert_that(
                calling(self.service.list_lines).with_args(s.tenant_uuid),
                raises(WazoConfdUnreachable),
            )

        self.confd.lines.list.side_effect = None
        self.confd.lines.list.return_value = {'total': 0, 'items': []}
        items, _, _ = self.service.list_lines(s.tenant_uuid)

        assert_that(items, equal_to([]))


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
