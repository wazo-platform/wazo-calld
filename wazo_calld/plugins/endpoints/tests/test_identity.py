# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from unittest import TestCase
from unittest.mock import Mock

from ari.exceptions import ARINotFound, ARIServerError
from hamcrest import assert_that, calling, equal_to, has_length, none, raises
from requests import HTTPError, ReadTimeout

from wazo_calld.exceptions import AsteriskARINotInitialized

from ..identity import (
    FAILURE_LOG_INTERVAL_SECONDS,
    FAILURE_MARK_SECONDS,
    RECENTLY_FAILED,
    RELOAD_WINDOW_SECONDS,
    EndpointIdentities,
    EndpointIdentity,
    IdentityMap,
)

TENANT = '00000000-0000-4000-8000-000000000001'
OTHER_TENANT = '00000000-0000-4000-8000-000000000002'


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def http_error(status):
    return HTTPError(response=Mock(status_code=status))


def ari_tuples(**variables):
    tuples = [
        {'attribute': 'type', 'value': 'endpoint'},
        {'attribute': 'context', 'value': 'default'},
    ]
    for name, value in variables.items():
        tuples.append({'attribute': 'set_var', 'value': f'{name}={value}'})
        tuples.append({'attribute': name, 'value': str(value)})
    return tuples


def wazo_tuples(line_id=None, trunk_id=None, tenant=TENANT):
    variables = {'__WAZO_TENANT_UUID': tenant}
    if line_id is not None:
        variables['WAZO_LINE_ID'] = line_id
    if trunk_id is not None:
        variables['WAZO_TRUNK_ID'] = trunk_id
    return ari_tuples(**variables)


class IdentitiesTestCase(TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.ari = Mock()
        self.confd = Mock()
        self.amid = Mock()
        self.identity_map = IdentityMap(clock=self.clock)
        self.identities = EndpointIdentities(
            self.identity_map, self.ari, self.confd, self.amid, clock=self.clock
        )
        self.get_object = self.ari.asterisk.getObject


class TestPJSIPIdentity(IdentitiesTestCase):
    def test_a_line_is_read_from_ari_once(self):
        self.get_object.return_value = wazo_tuples(line_id=12)

        first = self.identities.identity_of('PJSIP', 'abc')
        second = self.identities.identity_of('PJSIP', 'abc')

        expected = EndpointIdentity('line', 12, TENANT)
        assert_that(first, equal_to(expected))
        assert_that(second, equal_to(expected))
        self.get_object.assert_called_once_with(
            configClass='res_pjsip', objectType='endpoint', id='abc'
        )

    def test_a_trunk_is_read_from_ari_once(self):
        self.get_object.return_value = wazo_tuples(trunk_id=5, tenant=OTHER_TENANT)

        first = self.identities.identity_of('PJSIP', 'trunk-abc')
        second = self.identities.identity_of('PJSIP', 'trunk-abc')

        expected = EndpointIdentity('trunk', 5, OTHER_TENANT)
        assert_that(first, equal_to(expected))
        assert_that(second, equal_to(expected))
        assert_that(self.get_object.call_count, equal_to(1))

    def test_an_endpoint_with_no_wazo_id_is_read_once(self):
        self.get_object.return_value = ari_tuples(__WAZO_TENANT_UUID=TENANT)

        assert_that(self.identities.identity_of('PJSIP', 'guest'), none())
        assert_that(self.identities.identity_of('PJSIP', 'guest'), none())

        assert_that(self.get_object.call_count, equal_to(1))

    def test_an_endpoint_unknown_to_asterisk_is_read_once(self):
        self.get_object.side_effect = ARINotFound(self.ari, http_error(404))

        assert_that(self.identities.identity_of('PJSIP', 'gone'), none())
        self.clock.now += FAILURE_MARK_SECONDS
        assert_that(self.identities.identity_of('PJSIP', 'gone'), none())

        assert_that(self.get_object.call_count, equal_to(1))

    def test_an_endpoint_with_both_ids_is_an_error_stored_as_negative(self):
        self.get_object.return_value = wazo_tuples(line_id=1, trunk_id=2)

        with self.assertLogs('wazo_calld.plugins.endpoints.identity', 'ERROR'):
            result = self.identities.identity_of('PJSIP', 'both')
        assert_that(result, none())
        assert_that(self.identities.identity_of('PJSIP', 'both'), none())

        assert_that(self.get_object.call_count, equal_to(1))

    def test_an_id_without_tenant_is_an_error_stored_as_negative(self):
        self.get_object.return_value = ari_tuples(WAZO_LINE_ID=1)

        with self.assertLogs('wazo_calld.plugins.endpoints.identity', 'ERROR'):
            result = self.identities.identity_of('PJSIP', 'no-tenant')

        assert_that(result, none())

    def test_a_trunk_id_without_tenant_is_an_error_stored_as_negative(self):
        self.get_object.return_value = ari_tuples(WAZO_TRUNK_ID=5)

        with self.assertLogs('wazo_calld.plugins.endpoints.identity', 'ERROR'):
            result = self.identities.identity_of('PJSIP', 'no-tenant')

        assert_that(result, none())

    def test_an_id_that_is_not_a_number_is_an_error_stored_as_negative(self):
        self.get_object.return_value = ari_tuples(
            WAZO_LINE_ID='1a', __WAZO_TENANT_UUID=TENANT
        )

        with self.assertLogs('wazo_calld.plugins.endpoints.identity', 'ERROR'):
            result = self.identities.identity_of('PJSIP', 'bad-id')
        assert_that(result, none())
        assert_that(self.identities.identity_of('PJSIP', 'bad-id'), none())

        assert_that(self.get_object.call_count, equal_to(1))

    def test_a_trunk_id_that_is_not_a_number_is_an_error_stored_as_negative(self):
        self.get_object.return_value = ari_tuples(
            WAZO_TRUNK_ID='', __WAZO_TENANT_UUID=TENANT
        )

        with self.assertLogs('wazo_calld.plugins.endpoints.identity', 'ERROR'):
            result = self.identities.identity_of('PJSIP', 'bad-id')

        assert_that(result, none())

    def test_the_failure_mark_and_the_log_interval(self):
        assert_that(FAILURE_MARK_SECONDS, equal_to(30))
        assert_that(FAILURE_LOG_INTERVAL_SECONDS, equal_to(60))
        assert_that(RELOAD_WINDOW_SECONDS, equal_to(30))

    def test_a_server_error_blocks_reads_of_that_name_for_the_failure_mark(self):
        self.get_object.side_effect = ARIServerError(self.ari, http_error(500))

        assert_that(self.identities.identity_of('PJSIP', 'abc'), none())
        self.clock.now += FAILURE_MARK_SECONDS - 1
        assert_that(self.identities.identity_of('PJSIP', 'abc'), none())
        assert_that(self.get_object.call_count, equal_to(1))

        self.get_object.side_effect = None
        self.get_object.return_value = wazo_tuples(line_id=12)
        self.clock.now += 1
        result = self.identities.identity_of('PJSIP', 'abc')

        assert_that(result, equal_to(EndpointIdentity('line', 12, TENANT)))
        assert_that(self.get_object.call_count, equal_to(2))

    def test_a_failure_mark_is_per_name(self):
        self.get_object.side_effect = [
            ARIServerError(self.ari, http_error(500)),
            wazo_tuples(line_id=13),
        ]

        assert_that(self.identities.identity_of('PJSIP', 'abc'), none())
        result = self.identities.identity_of('PJSIP', 'def')

        assert_that(result, equal_to(EndpointIdentity('line', 13, TENANT)))

    def test_ari_not_initialized_is_a_failure(self):
        self.get_object.side_effect = AsteriskARINotInitialized()

        assert_that(self.identities.identity_of('PJSIP', 'abc'), none())
        assert_that(self.identities.identity_of('PJSIP', 'abc'), none())

        assert_that(self.get_object.call_count, equal_to(1))

    def test_an_unexpected_error_is_not_swallowed(self):
        self.get_object.side_effect = KeyError('attribute')

        assert_that(
            calling(self.identities.identity_of).with_args('PJSIP', 'abc'),
            raises(KeyError),
        )

    def test_failures_log_one_warning_per_class_per_minute(self):
        self.get_object.side_effect = ARIServerError(self.ari, http_error(500))

        with self.assertLogs(
            'wazo_calld.plugins.endpoints.identity', 'DEBUG'
        ) as captured:
            for index in range(100):
                self.identities.identity_of('PJSIP', f'endpoint-{index}')
                self.clock.now += 0.5

        warnings = [r for r in captured.records if r.levelno == logging.WARNING]
        assert_that(warnings, has_length(1))
        assert_that(self.get_object.call_count, equal_to(100))
        for record in warnings:
            assert 'endpoint-' not in record.getMessage()

    def test_the_next_warning_counts_the_failures_of_the_minute(self):
        self.get_object.side_effect = ARIServerError(self.ari, http_error(500))

        with self.assertLogs(
            'wazo_calld.plugins.endpoints.identity', 'WARNING'
        ) as captured:
            for index in range(100):
                self.identities.identity_of('PJSIP', f'endpoint-{index}')
                self.clock.now += 0.5
            self.clock.now = 1000.0 + FAILURE_LOG_INTERVAL_SECONDS
            self.identities.identity_of('PJSIP', 'endpoint-last')

        assert_that(captured.records, has_length(2))
        assert 'count=100 ' in captured.records[1].getMessage()
        assert 'status=500' in captured.records[1].getMessage()

    def test_two_failure_classes_log_one_warning_each(self):
        self.get_object.side_effect = [
            ARIServerError(self.ari, http_error(500)),
            ReadTimeout(),
            ARIServerError(self.ari, http_error(500)),
            ReadTimeout(),
        ]

        with self.assertLogs(
            'wazo_calld.plugins.endpoints.identity', 'WARNING'
        ) as captured:
            for index in range(4):
                self.identities.identity_of('PJSIP', f'endpoint-{index}')

        assert_that(captured.records, has_length(2))

    def test_other_technologies_are_never_looked_up(self):
        for techno in ('custom', 'Local', 'DAHDI'):
            assert_that(self.identities.identity_of(techno, 'abc'), none())

        self.get_object.assert_not_called()
        assert_that(self.confd.mock_calls, equal_to([]))


class TestConfdIdentity(IdentitiesTestCase):
    def test_an_iax2_trunk_is_read_from_confd_by_name_once(self):
        self.confd.endpoints_iax.list.return_value = {
            'total': 1,
            'items': [
                {'name': 'iax-1', 'tenant_uuid': TENANT, 'trunk': {'id': 7}},
            ],
        }

        first = self.identities.identity_of('IAX2', 'iax-1')
        second = self.identities.identity_of('IAX2', 'iax-1')

        expected = EndpointIdentity('trunk', 7, TENANT)
        assert_that(first, equal_to(expected))
        assert_that(second, equal_to(expected))
        self.confd.endpoints_iax.list.assert_called_once_with(
            name='iax-1', recurse=True
        )
        self.get_object.assert_not_called()

    def test_an_iax2_endpoint_without_trunk_is_negative(self):
        self.confd.endpoints_iax.list.return_value = {
            'total': 1,
            'items': [{'name': 'iax-1', 'tenant_uuid': TENANT, 'trunk': None}],
        }

        assert_that(self.identities.identity_of('IAX2', 'iax-1'), none())
        assert_that(self.identities.identity_of('IAX2', 'iax-1'), none())

        assert_that(self.confd.endpoints_iax.list.call_count, equal_to(1))

    def test_an_sccp_line_is_read_from_confd_by_name_once(self):
        self.confd.lines.list.return_value = {
            'total': 1,
            'items': [
                {
                    'id': 9,
                    'name': '1001',
                    'protocol': 'sccp',
                    'tenant_uuid': TENANT,
                },
            ],
        }

        first = self.identities.identity_of('SCCP', '1001')
        second = self.identities.identity_of('SCCP', '1001')

        expected = EndpointIdentity('line', 9, TENANT)
        assert_that(first, equal_to(expected))
        assert_that(second, equal_to(expected))
        self.confd.lines.list.assert_called_once_with(name='1001', recurse=True)

    def test_a_confd_item_without_tenant_is_negative(self):
        self.confd.lines.list.return_value = {
            'total': 1,
            'items': [{'id': 9, 'name': '1001', 'protocol': 'sccp'}],
        }
        self.confd.endpoints_iax.list.return_value = {
            'total': 1,
            'items': [{'name': 'iax-1', 'trunk': {'id': 7}}],
        }

        assert_that(self.identities.identity_of('SCCP', '1001'), none())
        assert_that(self.identities.identity_of('IAX2', 'iax-1'), none())
        assert_that(self.identities.identity_of('SCCP', '1001'), none())

        assert_that(self.confd.lines.list.call_count, equal_to(1))

    def test_a_line_of_another_protocol_with_that_name_is_not_an_sccp_line(self):
        self.confd.lines.list.return_value = {
            'total': 1,
            'items': [
                {'id': 9, 'name': '1001', 'protocol': 'sip', 'tenant_uuid': TENANT},
            ],
        }

        assert_that(self.identities.identity_of('SCCP', '1001'), none())

    def test_zero_items_is_negative(self):
        self.confd.lines.list.return_value = {'total': 0, 'items': []}
        self.confd.endpoints_iax.list.return_value = {'total': 0, 'items': []}

        assert_that(self.identities.identity_of('SCCP', '1001'), none())
        assert_that(self.identities.identity_of('SCCP', '1001'), none())
        assert_that(self.identities.identity_of('IAX2', 'iax-1'), none())
        assert_that(self.identities.identity_of('IAX2', 'iax-1'), none())

        assert_that(self.confd.lines.list.call_count, equal_to(1))
        assert_that(self.confd.endpoints_iax.list.call_count, equal_to(1))

    def test_a_confd_failure_is_a_failure_mark(self):
        self.confd.lines.list.side_effect = ReadTimeout()

        with self.assertLogs('wazo_calld.plugins.endpoints.identity', 'WARNING'):
            assert_that(self.identities.identity_of('SCCP', '1001'), none())
        assert_that(self.identities.identity_of('SCCP', '1001'), none())
        assert_that(self.confd.lines.list.call_count, equal_to(1))

        self.confd.lines.list.side_effect = None
        self.confd.lines.list.return_value = {
            'total': 1,
            'items': [
                {'id': 9, 'name': '1001', 'protocol': 'sccp', 'tenant_uuid': TENANT}
            ],
        }
        self.clock.now += FAILURE_MARK_SECONDS

        result = self.identities.identity_of('SCCP', '1001')

        assert_that(result, equal_to(EndpointIdentity('line', 9, TENANT)))


class TestGeneration(IdentitiesTestCase):
    def test_an_eviction_during_a_lookup_discards_its_answer(self):
        def evicted_while_reading(**kwargs):
            self.identity_map.evict('trunk', 5)
            return wazo_tuples(trunk_id=5)

        self.identity_map.write(
            ('PJSIP', 'other'), EndpointIdentity('trunk', 5, TENANT)
        )
        self.get_object.side_effect = evicted_while_reading

        self.identities.identity_of('PJSIP', 'abc')

        self.get_object.side_effect = None
        self.get_object.return_value = wazo_tuples(trunk_id=6)
        result = self.identities.identity_of('PJSIP', 'abc')

        assert_that(result, equal_to(EndpointIdentity('trunk', 6, TENANT)))
        assert_that(self.get_object.call_count, equal_to(2))

    def test_an_event_write_during_a_lookup_wins_over_its_answer(self):
        def written_while_reading(**kwargs):
            self.identity_map.write(
                ('PJSIP', 'abc'), EndpointIdentity('trunk', 6, TENANT)
            )
            return wazo_tuples(trunk_id=5)

        self.get_object.side_effect = written_while_reading

        self.identities.identity_of('PJSIP', 'abc')
        result = self.identities.identity_of('PJSIP', 'abc')

        assert_that(result, equal_to(EndpointIdentity('trunk', 6, TENANT)))
        assert_that(self.get_object.call_count, equal_to(1))

    def test_an_eviction_by_id_during_a_lookup_discards_another_identity(self):
        # the name was stored by another lookup, then its id evicted: the answer
        # read before, whatever identity it names, is older than that eviction
        def stored_then_evicted(**kwargs):
            _, generation = self.identity_map.lookup(('PJSIP', 'abc'))
            self.identity_map.store(
                ('PJSIP', 'abc'), EndpointIdentity('trunk', 5, TENANT), generation
            )
            self.identity_map.evict('trunk', 5)
            return wazo_tuples(trunk_id=6)

        self.get_object.side_effect = stored_then_evicted

        self.identities.identity_of('PJSIP', 'abc')
        assert_that(self.identities.identity_of('PJSIP', 'abc'), none())

        assert_that(self.get_object.call_count, equal_to(1))

    def test_an_event_write_during_a_failed_lookup_wins_over_its_mark(self):
        def written_then_failed(**kwargs):
            self.identity_map.write(
                ('PJSIP', 'abc'), EndpointIdentity('line', 3, TENANT)
            )
            raise ARIServerError(self.ari, http_error(500))

        self.get_object.side_effect = written_then_failed
        self.identities.identity_of('PJSIP', 'abc')

        result = self.identities.identity_of('PJSIP', 'abc')

        assert_that(result, equal_to(EndpointIdentity('line', 3, TENANT)))
        assert_that(self.get_object.call_count, equal_to(1))

    def test_the_eviction_stamps_are_dropped_when_no_lookup_is_in_flight(self):
        def evicted_while_reading(**kwargs):
            self.identity_map.evict('trunk', 5)
            self.identity_map.write(
                ('PJSIP', 'other'), EndpointIdentity('line', 1, TENANT)
            )
            assert_that(self.identity_map._name_evicted_at, has_length(2))
            assert_that(self.identity_map._id_evicted_at, has_length(3))
            return wazo_tuples(line_id=3)

        # a lookup answered from the map is never in flight
        self.identity_map.write(('PJSIP', 'held'), EndpointIdentity('line', 9, TENANT))
        self.identities.identity_of('PJSIP', 'held')
        self.get_object.side_effect = evicted_while_reading
        self.identities.identity_of('PJSIP', 'abc')

        assert_that(self.identity_map._name_evicted_at, equal_to({}))
        assert_that(self.identity_map._id_evicted_at, equal_to({}))

    def test_a_lookup_that_raises_leaves_no_lookup_in_flight(self):
        self.get_object.side_effect = KeyError('attribute')
        assert_that(
            calling(self.identities.identity_of).with_args('PJSIP', 'abc'),
            raises(KeyError),
        )

        self.identity_map.evict('trunk', 5)
        self.identities.identity_of('SIP', 'ignored')
        self.get_object.side_effect = None
        self.get_object.return_value = wazo_tuples(line_id=3)
        self.identities.identity_of('PJSIP', 'abc')

        assert_that(self.identity_map._id_evicted_at, equal_to({}))

    def test_a_stamp_is_kept_while_another_lookup_is_in_flight(self):
        def nested(**kwargs):
            self.get_object.side_effect = None
            self.get_object.return_value = wazo_tuples(trunk_id=5)
            # another thread's lookup ends while this one is in flight
            self.identity_map.evict('trunk', 5)
            self.identities.identity_of('PJSIP', 'other')
            return wazo_tuples(trunk_id=5)

        self.get_object.side_effect = nested
        self.identities.identity_of('PJSIP', 'abc')

        self.get_object.return_value = wazo_tuples(trunk_id=7)
        result = self.identities.identity_of('PJSIP', 'abc')

        assert_that(result, equal_to(EndpointIdentity('trunk', 7, TENANT)))


class TestEvictionWindow(IdentitiesTestCase):
    def test_an_evicted_name_is_not_read_during_the_reload_window(self):
        self.identity_map.write(('PJSIP', 'abc'), EndpointIdentity('trunk', 5, TENANT))
        self.get_object.return_value = wazo_tuples(trunk_id=5)

        self.identity_map.evict('trunk', 5)
        assert_that(self.identities.identity_of('PJSIP', 'abc'), none())
        self.clock.now += RELOAD_WINDOW_SECONDS - 1
        assert_that(self.identities.identity_of('PJSIP', 'abc'), none())
        self.get_object.assert_not_called()

        self.get_object.return_value = ari_tuples(__WAZO_TENANT_UUID=TENANT)
        self.clock.now += 1
        assert_that(self.identities.identity_of('PJSIP', 'abc'), none())

        assert_that(self.get_object.call_count, equal_to(1))

    def test_a_write_after_an_eviction_is_used_at_once(self):
        self.identity_map.write(('PJSIP', 'abc'), EndpointIdentity('trunk', 5, TENANT))
        self.identity_map.evict('trunk', 5)

        self.identity_map.write(('PJSIP', 'abc'), EndpointIdentity('trunk', 6, TENANT))

        result = self.identities.identity_of('PJSIP', 'abc')
        assert_that(result, equal_to(EndpointIdentity('trunk', 6, TENANT)))
        self.get_object.assert_not_called()

    def test_a_name_moved_off_its_id_by_a_write_is_not_read_in_the_window(self):
        line = EndpointIdentity('line', 1, TENANT)
        self.identity_map.write(('PJSIP', 'old'), line)
        self.identity_map.write(('PJSIP', 'new'), line)

        assert_that(self.identities.identity_of('PJSIP', 'old'), none())
        self.get_object.assert_not_called()


class TestClientUriFailure(IdentitiesTestCase):
    def test_an_amid_failure_blocks_reads_for_the_failure_mark(self):
        self.amid.action.side_effect = ReadTimeout()

        assert_that(self.identities.endpoint_of_client_uri('sip:a@p'), none())
        self.clock.now += FAILURE_MARK_SECONDS - 1
        assert_that(self.identities.endpoint_of_client_uri('sip:b@p'), none())
        assert_that(self.amid.action.call_count, equal_to(1))

        self.amid.action.side_effect = None
        self.amid.action.return_value = [
            {
                'Event': 'OutboundRegistrationDetail',
                'ClientUri': 'sip:a@p',
                'Endpoint': 'abc',
            }
        ]
        self.clock.now += 1
        assert_that(self.identities.endpoint_of_client_uri('sip:a@p'), equal_to('abc'))
        assert_that(self.amid.action.call_count, equal_to(2))

    def test_a_trunk_event_lifts_the_failure_mark(self):
        self.amid.action.side_effect = ReadTimeout()
        self.identities.endpoint_of_client_uri('sip:a@p')

        self.identity_map.forget_client_uris()
        self.identities.endpoint_of_client_uri('sip:a@p')

        assert_that(self.amid.action.call_count, equal_to(2))

    def test_a_failure_read_before_a_trunk_event_leaves_no_mark(self):
        def trunk_event_then_failed(action):
            self.identity_map.forget_client_uris()
            raise ReadTimeout()

        self.amid.action.side_effect = trunk_event_then_failed
        self.identities.endpoint_of_client_uri('sip:a@p')
        self.identities.endpoint_of_client_uri('sip:a@p')

        assert_that(self.amid.action.call_count, equal_to(2))


class TestClientUris(IdentitiesTestCase):
    def test_a_registration_list_read_before_a_trunk_event_is_dropped(self):
        def trunk_event_while_reading(action):
            self.identity_map.forget_client_uris()
            return [
                {
                    'Event': 'OutboundRegistrationDetail',
                    'ClientUri': 'sip:me@provider',
                    'Endpoint': 'old',
                }
            ]

        self.amid.action.side_effect = trunk_event_while_reading
        self.identities.endpoint_of_client_uri('sip:me@provider')
        self.identities.endpoint_of_client_uri('sip:me@provider')

        assert_that(self.amid.action.call_count, equal_to(2))


class TestRegistrationsWithoutEndpoint(IdentitiesTestCase):
    def test_a_registration_without_endpoint_names_no_endpoint(self):
        self.amid.action.return_value = [
            {'Event': 'OutboundRegistrationDetail', 'ClientUri': 'sip:a@provider'},
            {
                'Event': 'OutboundRegistrationDetail',
                'ClientUri': 'sip:b@provider',
                'Endpoint': '',
            },
        ]

        assert_that(self.identities.endpoint_of_client_uri('sip:a@provider'), none())
        assert_that(self.identities.endpoint_of_client_uri('sip:b@provider'), none())
        assert_that(self.identities.endpoint_of_client_uri('sip:a@provider'), none())

        assert_that(self.amid.action.call_count, equal_to(2))


class TestIdentityMap(TestCase):
    def setUp(self):
        self.identity_map = IdentityMap(clock=FakeClock())

    def test_evict_by_id_returns_every_name_it_held(self):
        trunk = EndpointIdentity('trunk', 5, TENANT)
        self.identity_map.store(('PJSIP', 'abc'), trunk, generation=0)
        self.identity_map.store(('PJSIP', 'def'), trunk, generation=0)

        evicted = self.identity_map.evict('trunk', 5)

        assert_that(sorted(evicted), equal_to([('PJSIP', 'abc'), ('PJSIP', 'def')]))
        assert_that(
            self.identity_map.lookup(('PJSIP', 'abc'))[0], equal_to(RECENTLY_FAILED)
        )
        assert_that(self.identity_map.evict('trunk', 5), equal_to([]))

    def test_a_write_moves_a_name_from_one_id_to_another(self):
        self.identity_map.write(('PJSIP', 'abc'), EndpointIdentity('trunk', 5, TENANT))
        self.identity_map.write(('PJSIP', 'abc'), EndpointIdentity('trunk', 6, TENANT))

        assert_that(self.identity_map.evict('trunk', 5), equal_to([]))
        assert_that(self.identity_map.evict('trunk', 6), equal_to([('PJSIP', 'abc')]))

    def test_a_write_evicts_the_older_name_of_that_id(self):
        line = EndpointIdentity('line', 1, TENANT)
        self.identity_map.write(('PJSIP', 'old'), line)
        self.identity_map.write(('PJSIP', 'new'), line)

        assert_that(
            self.identity_map.lookup(('PJSIP', 'old'))[0], equal_to(RECENTLY_FAILED)
        )
        assert_that(self.identity_map.lookup(('PJSIP', 'new'))[0], equal_to(line))

    def test_a_stale_generation_is_not_stored(self):
        written = EndpointIdentity('line', 2, TENANT)
        _, generation = self.identity_map.lookup(('PJSIP', 'abc'))
        self.identity_map.write(('PJSIP', 'abc'), written)

        stored = self.identity_map.store(
            ('PJSIP', 'abc'), EndpointIdentity('line', 1, TENANT), generation
        )

        assert_that(stored, equal_to(False))
        assert_that(self.identity_map.lookup(('PJSIP', 'abc'))[0], equal_to(written))

    def test_a_store_over_a_name_forgets_its_older_id(self):
        _, generation = self.identity_map.lookup(('PJSIP', 'abc'))
        moved = EndpointIdentity('line', 6, TENANT)
        self.identity_map.store(
            ('PJSIP', 'abc'), EndpointIdentity('line', 5, TENANT), generation
        )
        self.identity_map.store(('PJSIP', 'abc'), moved, generation)

        assert_that(self.identity_map.evict('line', 5), equal_to([]))
        assert_that(self.identity_map.lookup(('PJSIP', 'abc'))[0], equal_to(moved))
