# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import Mock

import requests
from hamcrest import assert_that, calling, equal_to, has_properties, none, not_, raises
from wazo_bus.resources.line.event import LineStatusUpdatedEvent
from wazo_bus.resources.trunk.event import TrunkStatusUpdatedEvent

from ..bus import EventHandler
from ..identity import EndpointIdentities, IdentityMap
from ..notifier import EndpointStatusNotifier
from ..services import Endpoint, NotifyingStatusCache, StatusCache
from .test_identity import TENANT, FakeClock, ari_tuples, wazo_tuples

OTHER_TENANT = '00000000-0000-4000-8000-000000000003'


class TestChannelEvents(TestCase):
    def setUp(self):
        endpoint = self.updated_endpoint = Mock(Endpoint)

        class StatusCacheMock(Mock):
            call_count = 0

            def assert_not_called(self):
                assert self.call_count == 0

            @contextmanager
            def update(self, techno, name):
                self.call_count += 1
                endpoint.techno = techno
                endpoint.name = name
                yield endpoint

        self.endpoint_status_cache = StatusCacheMock(StatusCache)
        self.identities = Mock()
        self.handler = EventHandler(self.endpoint_status_cache, Mock(), self.identities)

    def test_a_registry_for_a_client_uri_of_no_endpoint_touches_no_status(self):
        self.identities.endpoint_of_client_uri.return_value = None

        self.handler.on_registry(
            {'ChannelType': 'PJSIP', 'Username': 'sip:x@y', 'Status': 'Registered'}
        )

        self.endpoint_status_cache.assert_not_called()

    def test_on_peer_status_pjsip_registering(self):
        event = {
            'Event': 'PeerStatus',
            'Privilege': 'system,all',
            'ChannelType': 'PJSIP',
            'Peer': 'PJSIP/ycetqvtr',
            'PeerStatus': 'Reachable',
        }

        self.handler.on_peer_status(event)

        assert_that(
            self.updated_endpoint,
            has_properties(techno='PJSIP', name='ycetqvtr', registered=True),
        )

    def test_on_peer_status_pjsip_deregistering(self):
        event = {
            'Event': 'PeerStatus',
            'Privilege': 'system,all',
            'ChannelType': 'PJSIP',
            'Peer': 'PJSIP/ycetqvtr',
            'PeerStatus': 'Unreachable',
        }

        self.handler.on_peer_status(event)

        assert_that(
            self.updated_endpoint,
            has_properties(techno='PJSIP', name='ycetqvtr', registered=False),
        )

    def test_on_hangup(self):
        event = {
            'AccountCode': '',
            'CallerIDName': 'Alice',
            'CallerIDNum': '1001',
            'Cause': '16',
            'Cause-txt': 'Normal Clearing',
            'ChanVariable': {
                'WAZO_DEREFERENCED_USERUUID': '',
                'WAZO_SIP_CALL_ID': '779ffe58-7bf0-456f-8475-6195b88b6655',
                'XIVO_BASE_EXTEN': '2000',
                'WAZO_USERUUID': '',
            },
            'Channel': 'PJSIP/dev_370-00000002',
            'ChannelState': '6',
            'ChannelStateDesc': 'Up',
            'ConnectedLineName': '<unknown>',
            'ConnectedLineNum': '<unknown>',
            'Context': 'wazo-application',
            'Event': 'Hangup',
            'Exten': 's',
            'Language': 'en_US',
            'Linkedid': '1574445784.4',
            'Priority': '3',
            'Privilege': 'call,all',
            'Uniqueid': '1574445784.4',
        }

        self.handler.on_hangup(event)

        self.updated_endpoint.remove_call.assert_called_once_with('1574445784.4')
        assert_that(
            self.updated_endpoint, has_properties(techno='PJSIP', name='dev_370')
        )

    def test_on_hangup_ignores_local_channels(self):
        event = {
            'AccountCode': '',
            'CallerIDName': 'Alice',
            'CallerIDNum': '1001',
            'Cause': '16',
            'Cause-txt': 'Normal Clearing',
            'ChanVariable': {
                'WAZO_DEREFERENCED_USERUUID': '',
                'WAZO_SIP_CALL_ID': '779ffe58-7bf0-456f-8475-6195b88b6655',
                'XIVO_BASE_EXTEN': '2000',
                'WAZO_USERUUID': '',
            },
            'Channel': 'Local/1234@usersharedlines-0001',
            'ChannelState': '6',
            'ChannelStateDesc': 'Up',
            'ConnectedLineName': '<unknown>',
            'ConnectedLineNum': '<unknown>',
            'Context': 'wazo-application',
            'Event': 'Hangup',
            'Exten': 's',
            'Language': 'en_US',
            'Linkedid': '1574445784.4',
            'Priority': '3',
            'Privilege': 'call,all',
            'Uniqueid': '1574445784.4',
        }

        self.handler.on_hangup(event)

        self.endpoint_status_cache.assert_not_called()

    def test_on_new_channel(self):
        event = {
            'AccountCode': '',
            'CallerIDName': 'Alice',
            'CallerIDNum': '1001',
            'ChanVariable': {
                'WAZO_DEREFERENCED_USERUUID': '',
                'WAZO_SIP_CALL_ID': '',
                'XIVO_BASE_EXTEN': '',
                'WAZO_USERUUID': '',
            },
            'Channel': 'PJSIP/dev_370-00000002',
            'ChannelState': '4',
            'ChannelStateDesc': 'Ring',
            'ConnectedLineName': '<unknown>',
            'ConnectedLineNum': '<unknown>',
            'Context': 'from-extern',
            'Event': 'Newchannel',
            'Exten': '2000',
            'Language': 'en',
            'Linkedid': '1574445784.4',
            'Priority': '1',
            'Privilege': 'call,all',
            'Uniqueid': '1574445784.4',
        }

        self.handler.on_new_channel(event)

        self.updated_endpoint.add_call.assert_called_once_with('1574445784.4')
        assert_that(
            self.updated_endpoint, has_properties(techno='PJSIP', name='dev_370')
        )

    def test_on_new_channel_ignore_local_channels(self):
        event = {
            'AccountCode': '',
            'CallerIDName': 'Alice',
            'CallerIDNum': '1001',
            'ChanVariable': {
                'WAZO_DEREFERENCED_USERUUID': '',
                'WAZO_SIP_CALL_ID': '',
                'XIVO_BASE_EXTEN': '',
                'WAZO_USERUUID': '',
            },
            'Channel': 'Local/1234@usersharedlines-0001',
            'ChannelState': '4',
            'ChannelStateDesc': 'Ring',
            'ConnectedLineName': '<unknown>',
            'ConnectedLineNum': '<unknown>',
            'Context': 'from-extern',
            'Event': 'Newchannel',
            'Exten': '2000',
            'Language': 'en',
            'Linkedid': '1574445784.4',
            'Priority': '1',
            'Privilege': 'call,all',
            'Uniqueid': '1574445784.4',
        }

        self.handler.on_new_channel(event)

        self.endpoint_status_cache.assert_not_called()


def line_sip_associated(line_id, name, tenant_uuid=TENANT):
    return {
        'line': {'id': line_id, 'tenant_uuid': tenant_uuid},
        'endpoint_sip': {'name': name, 'auth_section_options': [['username', name]]},
    }


def trunk_sip_associated(trunk_id, name, tenant_uuid=TENANT):
    return {
        'trunk': {'id': trunk_id, 'tenant_uuid': tenant_uuid},
        'endpoint_sip': {
            'name': name,
            'registration_section_options': [['client_uri', f'sip:{name}@example']],
        },
    }


def sip_updated(name, line_id=None, trunk_id=None, tenant_uuid=TENANT):
    return {
        'name': name,
        'tenant_uuid': tenant_uuid,
        'auth_section_options': [],
        'registration_section_options': [],
        'line': {'id': line_id} if line_id else None,
        'trunk': {'id': trunk_id} if trunk_id else None,
    }


def registry(uri, status='Registered', techno='PJSIP'):
    return {
        'Event': 'Registry',
        'ChannelType': techno,
        'Domain': 'sip:gateway.example.com',
        'Status': status,
        'Username': uri,
    }


def registration(uri, endpoint):
    return {
        'Event': 'OutboundRegistrationDetail',
        'ObjectType': 'registration',
        'ClientUri': uri,
        'Endpoint': endpoint,
    }


class TestStatusPublishedFromIdentity(TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.ari = Mock()
        self.ari.endpoints.list.return_value = []
        self.confd = Mock()
        self.amid = Mock()
        self.amid.action.return_value = []
        self.publisher = Mock()
        self.identity_map = IdentityMap(clock=self.clock)
        self.identities = EndpointIdentities(
            self.identity_map, self.ari, self.confd, self.amid, clock=self.clock
        )
        notifier = EndpointStatusNotifier(self.publisher, self.identities)
        self.status_cache = NotifyingStatusCache(notifier.endpoint_updated, self.ari)
        for techno, name in [
            ('PJSIP', 'abc'),
            ('PJSIP', 'line-a'),
            ('PJSIP', 'guest'),
            ('IAX2', 'iax-a'),
            ('SCCP', '1001'),
        ]:
            self.status_cache.add_endpoint(Endpoint(techno, name, False, []))
        self.handler = EventHandler(
            self.status_cache, self.identity_map, self.identities
        )
        self.get_object = self.ari.asterisk.getObject

    def peer_status(self, name, status='Reachable'):
        # the opposite status first, without publishing, so that the event is a change
        self.status_cache.get('PJSIP', name).registered = status != 'Reachable'
        self.handler.on_peer_status({'Peer': f'PJSIP/{name}', 'PeerStatus': status})

    def new_channel(self, techno, name):
        self.handler.on_new_channel(
            {'Channel': f'{techno}/{name}-00000001', 'Uniqueid': str(self.clock.now)}
        )
        self.clock.now += 1

    def published(self):
        events = [c.args[0] for c in self.publisher.publish.call_args_list]
        self.publisher.publish.reset_mock()
        return events

    def published_ids(self):
        return [(event.name, event.content['id']) for event in self.published()]

    def test_a_line_status_is_published_with_the_identity_from_ari(self):
        self.get_object.return_value = wazo_tuples(line_id=12)

        self.peer_status('line-a')
        self.peer_status('line-a', 'Unreachable')

        assert_that(
            self.published(),
            equal_to(
                [
                    LineStatusUpdatedEvent(12, 'sip', 'line-a', True, 0, TENANT),
                    LineStatusUpdatedEvent(12, 'sip', 'line-a', False, 0, TENANT),
                ]
            ),
        )
        assert_that(self.get_object.call_count, equal_to(1))
        assert_that(self.confd.mock_calls, equal_to([]))

    def test_a_trunk_status_is_published_with_the_identity_from_ari(self):
        self.get_object.return_value = wazo_tuples(trunk_id=5, tenant=OTHER_TENANT)

        self.peer_status('abc')
        self.peer_status('abc')

        assert_that(
            self.published(),
            equal_to(
                [
                    TrunkStatusUpdatedEvent(5, 'sip', 'abc', True, 0, OTHER_TENANT),
                    TrunkStatusUpdatedEvent(5, 'sip', 'abc', True, 0, OTHER_TENANT),
                ]
            ),
        )
        assert_that(self.get_object.call_count, equal_to(1))

    def test_nothing_is_published_for_a_negative_or_a_failure(self):
        self.get_object.return_value = ari_tuples(__WAZO_TENANT_UUID=TENANT)
        self.peer_status('guest')
        self.confd.lines.list.return_value = {'items': []}
        self.new_channel('SCCP', '1001')
        self.new_channel('custom', 'xyz')

        assert_that(self.published(), equal_to([]))

    def test_iax2_and_sccp_publish_from_one_confd_request_each(self):
        self.confd.endpoints_iax.list.return_value = {
            'items': [{'name': 'iax-a', 'tenant_uuid': TENANT, 'trunk': {'id': 8}}]
        }
        self.confd.lines.list.return_value = {
            'items': [
                {'id': 9, 'name': '1001', 'protocol': 'sccp', 'tenant_uuid': TENANT}
            ]
        }

        for _ in range(2):
            self.new_channel('IAX2', 'iax-a')
            self.new_channel('SCCP', '1001')

        assert_that(
            self.published_ids(),
            equal_to(
                [
                    ('trunk_status_updated', 8),
                    ('line_status_updated', 9),
                    ('trunk_status_updated', 8),
                    ('line_status_updated', 9),
                ]
            ),
        )
        self.confd.endpoints_iax.list.assert_called_once_with(
            name='iax-a', recurse=True
        )
        self.confd.lines.list.assert_called_once_with(name='1001', recurse=True)
        self.get_object.assert_not_called()

    def test_an_association_writes_the_identity_without_reading_ari(self):
        self.handler.on_line_endpoint_sip_associated(line_sip_associated(3, 'abc'))

        self.peer_status('abc')

        assert_that(self.published_ids(), equal_to([('line_status_updated', 3)]))
        self.get_object.assert_not_called()

    def test_an_association_replaces_a_negative(self):
        self.get_object.return_value = ari_tuples(__WAZO_TENANT_UUID=TENANT)
        self.peer_status('abc')
        assert_that(self.published(), equal_to([]))

        self.handler.on_trunk_endpoint_sip_associated(trunk_sip_associated(4, 'abc'))
        self.peer_status('abc')

        assert_that(self.published_ids(), equal_to([('trunk_status_updated', 4)]))
        assert_that(self.get_object.call_count, equal_to(1))

    def test_a_sip_endpoint_update_writes_the_identity_without_reading_ari(self):
        self.handler.on_endpoint_sip_updated(sip_updated('abc', trunk_id=6))
        self.peer_status('abc')
        self.handler.on_endpoint_sip_updated(sip_updated('line-a', line_id=7))
        self.peer_status('line-a')

        assert_that(
            self.published_ids(),
            equal_to([('trunk_status_updated', 6), ('line_status_updated', 7)]),
        )
        self.get_object.assert_not_called()

    def test_an_iax_update_and_an_sccp_edit_write_the_identity(self):
        self.handler.on_trunk_endpoint_iax_updated(
            {'name': 'iax-a', 'tenant_uuid': TENANT, 'trunk': {'id': 11}}
        )
        self.handler.on_line_edited(
            {'id': 12, 'name': '1001', 'protocol': 'sccp', 'tenant_uuid': TENANT}
        )
        self.new_channel('IAX2', 'iax-a')
        self.new_channel('SCCP', '1001')

        assert_that(
            self.published_ids(),
            equal_to([('trunk_status_updated', 11), ('line_status_updated', 12)]),
        )
        assert_that(self.confd.mock_calls, equal_to([]))

    def test_a_sip_line_edit_writes_nothing(self):
        self.handler.on_line_edited(
            {'id': 12, 'name': '1001', 'protocol': 'sip', 'tenant_uuid': TENANT}
        )
        self.confd.lines.list.return_value = {
            'items': [
                {'id': 13, 'name': '1001', 'protocol': 'sccp', 'tenant_uuid': TENANT}
            ]
        }

        self.new_channel('SCCP', '1001')

        assert_that(self.published_ids(), equal_to([('line_status_updated', 13)]))

    def test_associations_of_sccp_and_iax_write_the_identity(self):
        self.handler.on_line_endpoint_sccp_associated(
            {
                'line': {'id': 14, 'name': '1001', 'tenant_uuid': TENANT},
                'endpoint_sccp': {'id': 1},
            }
        )
        self.handler.on_trunk_endpoint_iax_associated(
            {
                'trunk': {'id': 15, 'tenant_uuid': TENANT},
                'endpoint_iax': {'name': 'iax-b'},
            }
        )
        self.new_channel('SCCP', '1001')
        self.new_channel('IAX2', 'iax-b')

        assert_that(
            self.published_ids(),
            equal_to([('line_status_updated', 14), ('trunk_status_updated', 15)]),
        )
        assert_that(self.confd.mock_calls, equal_to([]))

    def test_an_association_tracks_the_new_endpoint_status(self):
        self.handler.on_trunk_endpoint_sip_associated(trunk_sip_associated(4, 'new'))
        self.handler.on_trunk_endpoint_iax_associated(
            {'trunk': {'id': 5, 'tenant_uuid': TENANT}, 'endpoint_iax': {'name': 'x'}}
        )
        self.handler.on_line_endpoint_sip_associated(line_sip_associated(6, 'l'))

        for techno, name in [('PJSIP', 'new'), ('IAX2', 'x'), ('PJSIP', 'l')]:
            assert_that(
                self.status_cache.get(techno, name),
                has_properties(techno=techno, name=name, registered=False),
            )

    def test_a_deleted_line_name_reused_publishes_the_new_id(self):
        self.get_object.return_value = wazo_tuples(line_id=1)
        self.peer_status('abc')

        self.handler.on_line_endpoint_deleted({'id': 1})
        self.get_object.return_value = wazo_tuples(line_id=2)
        self.peer_status('abc')

        assert_that(
            self.published_ids(),
            equal_to([('line_status_updated', 1), ('line_status_updated', 2)]),
        )

    def test_a_dissociation_evicts_the_identity(self):
        self.get_object.return_value = wazo_tuples(line_id=1)
        self.peer_status('line-a')
        self.get_object.return_value = wazo_tuples(trunk_id=5)
        self.peer_status('abc')
        self.published()

        self.handler.on_line_endpoint_dissociated({'line': {'id': 1}})
        self.handler.on_trunk_endpoint_dissociated({'trunk': {'id': 5}})
        self.get_object.return_value = ari_tuples(__WAZO_TENANT_UUID=TENANT)
        self.peer_status('line-a')
        self.peer_status('abc')

        assert_that(self.published(), equal_to([]))
        assert_that(self.get_object.call_count, equal_to(4))

    def test_a_dissociation_leaves_the_other_kind_alone(self):
        self.handler.on_line_endpoint_sip_associated(line_sip_associated(5, 'line-a'))

        self.handler.on_trunk_endpoint_dissociated({'trunk': {'id': 5}})
        self.peer_status('line-a')

        assert_that(self.published_ids(), equal_to([('line_status_updated', 5)]))

    def test_a_deleted_trunk_is_evicted_and_its_status_dropped(self):
        self.get_object.return_value = wazo_tuples(trunk_id=5)
        self.peer_status('abc')

        self.handler.on_trunk_endpoint_deleted({'id': 5})

        assert_that(self.status_cache.get('PJSIP', 'abc'), none())
        assert_that(self.status_cache.get('PJSIP', 'line-a'), not_(none()))

    def test_a_deleted_unknown_trunk_drops_no_status(self):
        self.handler.on_trunk_endpoint_deleted({'id': 5})

        assert_that(self.status_cache.get('PJSIP', 'abc'), not_(none()))

    def test_a_name_moved_to_another_trunk_publishes_the_new_trunk(self):
        self.get_object.return_value = wazo_tuples(trunk_id=5)
        self.peer_status('abc')

        self.handler.on_trunk_endpoint_dissociated({'trunk': {'id': 5}})
        self.handler.on_trunk_endpoint_sip_associated(trunk_sip_associated(6, 'abc'))
        self.peer_status('abc')

        assert_that(
            self.published_ids(),
            equal_to([('trunk_status_updated', 5), ('trunk_status_updated', 6)]),
        )
        assert_that(self.get_object.call_count, equal_to(1))

    def test_a_name_moved_by_an_endpoint_update_publishes_the_new_trunk(self):
        self.get_object.return_value = wazo_tuples(trunk_id=5)
        self.peer_status('abc')

        self.handler.on_endpoint_sip_updated(sip_updated('abc', trunk_id=6))
        self.peer_status('abc')

        assert_that(
            self.published_ids(),
            equal_to([('trunk_status_updated', 5), ('trunk_status_updated', 6)]),
        )

    def test_a_registry_rebuilds_the_client_uri_index_once_per_unknown_uri(self):
        self.amid.action.return_value = [
            {'Event': 'Response', 'Response': 'Success'},
            registration('sip:me@provider', 'abc'),
            # an event of the list that is not a registration, naming an endpoint
            {'Event': 'AuthDetail', 'ObjectType': 'auth', 'Endpoint': 'abc'},
            {'Event': 'OutboundRegistrationDetailComplete'},
        ]
        self.get_object.return_value = wazo_tuples(trunk_id=5, tenant=OTHER_TENANT)

        self.handler.on_registry(registry('sip:me@provider'))
        self.handler.on_registry(registry('sip:me@provider', 'Unregistered'))

        assert_that(
            self.published(),
            equal_to(
                [
                    TrunkStatusUpdatedEvent(5, 'sip', 'abc', True, 0, OTHER_TENANT),
                    TrunkStatusUpdatedEvent(5, 'sip', 'abc', False, 0, OTHER_TENANT),
                ]
            ),
        )
        self.amid.action.assert_called_once_with('PJSIPShowRegistrationsOutbound')
        assert_that(self.confd.mock_calls, equal_to([]))

    def test_an_unknown_uri_is_not_read_again_until_a_trunk_event(self):
        self.amid.action.return_value = [registration('sip:me@provider', 'abc')]
        self.get_object.return_value = wazo_tuples(trunk_id=5)
        self.handler.on_registry(registry('sip:me@provider'))
        self.handler.on_registry(registry('sip:other@provider'))
        assert_that(self.amid.action.call_count, equal_to(2))

        self.handler.on_registry(registry('sip:other@provider'))
        self.handler.on_line_endpoint_deleted({'id': 1})
        self.handler.on_registry(registry('sip:other@provider'))
        self.handler.on_line_endpoint_sip_associated(line_sip_associated(2, 'l'))
        self.handler.on_registry(registry('sip:other@provider'))
        self.handler.on_endpoint_sip_updated(sip_updated('l', line_id=2))
        self.handler.on_registry(registry('sip:other@provider'))
        self.handler.on_line_endpoint_dissociated({'line': {'id': 2}})
        self.handler.on_registry(registry('sip:other@provider'))
        assert_that(self.amid.action.call_count, equal_to(2))

        self.handler.on_trunk_endpoint_sip_associated(trunk_sip_associated(9, 'z'))
        self.handler.on_registry(registry('sip:other@provider'))

        assert_that(self.amid.action.call_count, equal_to(3))

    def test_every_trunk_event_clears_the_unknown_uris(self):
        trunk_events = [
            ('on_trunk_endpoint_deleted', {'id': 9}),
            ('on_trunk_endpoint_sip_associated', trunk_sip_associated(9, 'z')),
            (
                'on_trunk_endpoint_iax_associated',
                {
                    'trunk': {'id': 9, 'tenant_uuid': TENANT},
                    'endpoint_iax': {'name': 'z'},
                },
            ),
            (
                'on_trunk_endpoint_custom_associated',
                {'trunk': {'id': 9, 'tenant_uuid': TENANT}, 'endpoint_custom': {}},
            ),
            ('on_trunk_endpoint_dissociated', {'trunk': {'id': 9}}),
            ('on_endpoint_sip_updated', sip_updated('z', trunk_id=9)),
            (
                'on_trunk_endpoint_iax_updated',
                {'name': 'z', 'tenant_uuid': TENANT, 'trunk': {'id': 9}},
            ),
        ]
        self.handler.on_registry(registry('sip:other@provider'))

        for handler_name, event in trunk_events:
            calls = self.amid.action.call_count
            getattr(self.handler, handler_name)(event)
            self.handler.on_registry(registry('sip:other@provider'))
            self.handler.on_registry(registry('sip:other@provider'))
            assert self.amid.action.call_count == calls + 1, handler_name

    def test_an_iax_update_without_trunk_keeps_the_unknown_uris(self):
        self.handler.on_registry(registry('sip:other@provider'))

        self.handler.on_trunk_endpoint_iax_updated(
            {'name': 'z', 'tenant_uuid': TENANT, 'trunk': None}
        )
        self.handler.on_registry(registry('sip:other@provider'))

        assert_that(self.amid.action.call_count, equal_to(1))

    def test_a_registry_for_a_uri_that_stays_unknown_raises_nothing(self):
        for status in ('Registered', 'Unregistered', 'Rejected'):
            assert_that(
                calling(self.handler.on_registry).with_args(
                    registry('sip:nobody@provider', status)
                ),
                not_(raises(Exception)),
            )

        assert_that(self.published(), equal_to([]))

    def test_amid_failing_publishes_nothing_and_warns(self):
        self.amid.action.side_effect = requests.ConnectionError

        with self.assertLogs(
            'wazo_calld.plugins.endpoints.identity', 'WARNING'
        ) as captured:
            self.handler.on_registry(registry('sip:me@provider'))

        assert_that(self.published(), equal_to([]))
        for record in captured.records:
            assert 'sip:me@provider' not in record.getMessage()

    def test_an_iax2_registry_resolves_by_confd(self):
        self.confd.endpoints_iax.list.return_value = {
            'items': [{'name': 'iax-a', 'tenant_uuid': TENANT, 'trunk': {'id': 8}}]
        }

        self.handler.on_registry(
            registry('iax2:iax-a@provider', 'Registered', techno='IAX2')
        )

        assert_that(self.published_ids(), equal_to([('trunk_status_updated', 8)]))
        self.amid.action.assert_not_called()

    def test_a_misconfigured_iax2_registry_is_ignored(self):
        self.handler.on_registry(registry('trunkwazomd6', 'Rejected', techno='IAX2'))

        assert_that(self.published(), equal_to([]))
        assert_that(self.confd.mock_calls, equal_to([]))

    def test_a_registry_of_another_technology_is_ignored(self):
        self.handler.on_registry(registry('x', techno='SIP'))

        self.amid.action.assert_not_called()
        assert_that(self.confd.mock_calls, equal_to([]))


class TestNoBulkLoad(TestCase):
    """Every handler, driven once: no confd request for a PJSIP endpoint, no bulk list."""

    def test_no_handler_loads_every_line_or_trunk(self):
        ari = Mock()
        ari.asterisk.getObject.return_value = wazo_tuples(trunk_id=5)
        confd = Mock()
        confd.lines.list.return_value = {'items': []}
        confd.endpoints_iax.list.return_value = {'items': []}
        amid = Mock()
        amid.action.return_value = [registration('sip:me@provider', 'abc')]
        identity_map = IdentityMap()
        identities = EndpointIdentities(identity_map, ari, confd, amid)
        notifier = EndpointStatusNotifier(Mock(), identities)
        status_cache = NotifyingStatusCache(notifier.endpoint_updated, ari)
        status_cache.add_endpoint(Endpoint('PJSIP', 'abc', False, []))
        handler = EventHandler(status_cache, identity_map, identities)
        consumer = Mock()
        handler.subscribe(consumer)
        subscribed = {c.args[0]: c.args[1] for c in consumer.subscribe.call_args_list}
        payload = {
            'id': 1,
            'name': 'abc',
            'protocol': 'sip',
            'tenant_uuid': TENANT,
            'interface': 'x',
            'auth_section_options': [],
            'registration_section_options': [],
            'line': {'id': 1, 'tenant_uuid': TENANT, 'name': 'abc'},
            'trunk': {'id': 5, 'tenant_uuid': TENANT},
            'endpoint_sip': {
                'name': 'abc',
                'auth_section_options': [],
                'registration_section_options': [],
            },
            'endpoint_iax': {'name': 'abc'},
            'endpoint_sccp': {'id': 1},
            'endpoint_custom': {'interface': 'x'},
            'Peer': 'PJSIP/abc',
            'PeerStatus': 'Reachable',
            'Channel': 'PJSIP/abc-00000001',
            'Uniqueid': '1.1',
            'ChannelType': 'PJSIP',
            'Status': 'Registered',
            'Username': 'sip:me@provider',
        }

        for name in sorted(subscribed):
            subscribed[name](dict(payload))
            identity_map.evict('trunk', 5)
            identity_map.evict('line', 1)
            identity_map.forget_client_uris()

        assert_that(len(subscribed), equal_to(20))
        assert_that(confd.mock_calls, equal_to([]))
        assert ari.asterisk.getObject.called
