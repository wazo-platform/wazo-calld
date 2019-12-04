# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import Mock
from hamcrest import assert_that, has_properties

from ..bus import EventHandler
from ..services import Endpoint, ConfdCache


class TestOnPeerStatus(TestCase):
    def setUp(self):
        endpoint = self.updated_endpoint = Mock(Endpoint)

        class StatusCacheMock:
            @contextmanager
            def update(self, techno, name):
                endpoint.techno = techno
                endpoint.name = name
                yield endpoint

        self.endpoint_status_cache = StatusCacheMock()
        self.confd_cache = Mock(ConfdCache)
        self.handler = EventHandler(self.endpoint_status_cache, self.confd_cache)

    def test_on_trunk_registering(self):
        self.confd_cache.get_trunk_by_username.return_value = {'name': 'foobar'}
        event = {
            'ChannelType': 'PJSIP',
            'Domain': 'sip:wazo-dev-gateway.lan.wazo.io',
            'Event': 'Registry',
            'Privilege': 'system,all',
            'Status': 'Registered',
            'Username': 'sip:dev_370@wazo-dev-gateway.lan.wazo.io',
        }

        self.handler.on_registry(event)

        assert_that(
            self.updated_endpoint,
            has_properties(techno='PJSIP', name='foobar', registered=True),
        )

    def test_on_trunk_deregistering(self):
        self.confd_cache.get_trunk_by_username.return_value = {'name': 'foobar'}
        event = {
            'ChannelType': 'PJSIP',
            'Domain': 'sip:wazo-dev-gateway.lan.wazo.io',
            'Event': 'Registry',
            'Privilege': 'system,all',
            'Status': 'Unregistered',
            'Username': 'sip:dev_370@wazo-dev-gateway.lan.wazo.io',
        }

        self.handler.on_registry(event)

        assert_that(
            self.updated_endpoint,
            has_properties(techno='PJSIP', name='foobar', registered=False),
        )

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
                'XIVO_USERUUID': '',
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
        assert_that(self.updated_endpoint, has_properties(techno='PJSIP', name='dev_370'))

    def test_on_new_channel(self):
        event = {
            'AccountCode': '',
            'CallerIDName': 'Alice',
            'CallerIDNum': '1001',
            'ChanVariable': {
                'WAZO_DEREFERENCED_USERUUID': '',
                'WAZO_SIP_CALL_ID': '',
                'XIVO_BASE_EXTEN': '',
                'XIVO_USERUUID': '',
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
        assert_that(self.updated_endpoint, has_properties(techno='PJSIP', name='dev_370'))

    def test_on_trunk_endpoint_sip_associated(self):
        trunk_id = 42
        tenant_uuid = '2c34c282-433e-4bb8-8d56-fec14ff7e1e9'
        name = 'the-name'
        username = 'the-username'

        event = {
            'endpoint_sip': {
                'id': 45,
                'name': name,
                'tenant_uuid': tenant_uuid,
                'username': username,
            },
            'trunk': {
                'id': trunk_id,
                'tenant_uuid': tenant_uuid,
            },
        }

        self.handler.on_trunk_endpoint_sip_associated(event)

        self.confd_cache.add_trunk.assert_called_once_with(
            'sip', trunk_id, name, username, tenant_uuid,
        )

    def test_on_trunk_endpoint_iax_associated(self):
        trunk_id = 42
        tenant_uuid = '2c34c282-433e-4bb8-8d56-fec14ff7e1e9'
        name = 'the-name'

        event = {
            'endpoint_iax': {
                'id': 45,
                'name': name,
                'tenant_uuid': tenant_uuid,
            },
            'trunk': {
                'id': trunk_id,
                'tenant_uuid': tenant_uuid,
            },
        }

        self.handler.on_trunk_endpoint_iax_associated(event)

        self.confd_cache.add_trunk.assert_called_once_with(
            'iax', trunk_id, name, None, tenant_uuid,
        )

    def test_on_trunk_endpoint_custom_associated(self):
        trunk_id = 42
        tenant_uuid = '2c34c282-433e-4bb8-8d56-fec14ff7e1e9'
        interface = 'interface'

        event = {
            'endpoint_custom': {
                'id': 45,
                'interface': interface,
                'tenant_uuid': tenant_uuid,
            },
            'trunk': {
                'id': trunk_id,
                'tenant_uuid': tenant_uuid,
            },
        }

        self.handler.on_trunk_endpoint_custom_associated(event)

        self.confd_cache.add_trunk.assert_called_once_with(
            'custom', trunk_id, interface, None, tenant_uuid,
        )

    def test_on_trunk_endpoint_sip_dissociated(self):
        trunk_id = 42
        event = {'trunk': {'id': trunk_id}}

        self.handler.on_trunk_endpoint_dissociated(event)

        self.confd_cache.delete_trunk.assert_called_once_with(trunk_id)

    def test_on_trunk_endpoint_iax_dissociated(self):
        trunk_id = 42
        event = {'trunk': {'id': trunk_id}}

        self.handler.on_trunk_endpoint_dissociated(event)

        self.confd_cache.delete_trunk.assert_called_once_with(trunk_id)

    def test_on_trunk_endpoint_custom_dissociated(self):
        trunk_id = 42
        event = {'trunk': {'id': trunk_id}}

        self.handler.on_trunk_endpoint_dissociated(event)

        self.confd_cache.delete_trunk.assert_called_once_with(trunk_id)

    def test_on_trunk_deleted(self):
        event = {'id': 42}

        self.handler.on_trunk_deleted(event)

        self.confd_cache.delete_trunk.assert_called_once_with(42)

    def test_on_trunk_updated(self):
        event = {'id': 42}

        self.handler.on_trunk_updated(event)

        self.confd_cache.update_trunk.assert_called_once_with(42)
