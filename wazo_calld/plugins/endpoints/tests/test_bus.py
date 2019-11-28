# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock

from ..bus import EventHandler
from ..services import EndpointsService


class TestOnPeerStatus(TestCase):
    def setUp(self):
        self.endpoints_service = Mock(EndpointsService)
        self.handler = EventHandler(self.endpoints_service)

    def test_on_trunk_registering(self):
        event = {
            'ChannelType': 'PJSIP',
            'Domain': 'sip:wazo-dev-gateway.lan.wazo.io',
            'Event': 'Registry',
            'Privilege': 'system,all',
            'Status': 'Registered',
            'Username': 'sip:dev_370@wazo-dev-gateway.lan.wazo.io',
        }

        self.handler.on_registry(event)

        self.endpoints_service.update_trunk_endpoint.assert_called_once_with(
            'PJSIP', 'dev_370', registered=True,
        )

    def test_on_trunk_deregistering(self):
        event = {
            'ChannelType': 'PJSIP',
            'Domain': 'sip:wazo-dev-gateway.lan.wazo.io',
            'Event': 'Registry',
            'Privilege': 'system,all',
            'Status': 'Unregistered',
            'Username': 'sip:dev_370@wazo-dev-gateway.lan.wazo.io',
        }

        self.handler.on_registry(event)

        self.endpoints_service.update_trunk_endpoint.assert_called_once_with(
            'PJSIP', 'dev_370', registered=False,
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

        self.endpoints_service.update_line_endpoint.assert_called_once_with(
            'PJSIP', 'ycetqvtr', registered=True,
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

        self.endpoints_service.update_line_endpoint.assert_called_once_with(
            'PJSIP', 'ycetqvtr', registered=False,
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

        self.endpoints_service.remove_call.assert_called_once_with(
            'PJSIP', 'dev_370', '1574445784.4',
        )

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

        self.endpoints_service.add_call.assert_called_once_with(
            'PJSIP', 'dev_370', '1574445784.4',
        )
