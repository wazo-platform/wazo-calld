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

    def test_on_peer_status_pjsip_registering(self):
        event = {
            'Event': 'PeerStatus',
            'Privilege': 'system,all',
            'ChannelType': 'PJSIP',
            'Peer': 'PJSIP/ycetqvtr',
            'PeerStatus': 'Reachable',
        }

        self.handler.on_peer_status(event)

        self.endpoints_service.update_endpoint.assert_called_once_with(
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

        self.endpoints_service.update_endpoint.assert_called_once_with(
            'PJSIP', 'ycetqvtr', registered=False,
        )
