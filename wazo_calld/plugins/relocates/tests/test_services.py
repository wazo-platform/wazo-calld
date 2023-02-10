# Copyright 2019-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import (
    Mock,
    sentinel as s,
)

from hamcrest import (
    assert_that,
    equal_to,
)

from ..services import InterfaceDestination


class TestInterfaceDestination(TestCase):
    def setUp(self):
        self.ari = Mock()

    def test_ari_endpoint_sccp(self):
        interface = 'sccp/foobar'
        details = {'interface': interface, 'line_id': 42}
        destination = InterfaceDestination(self.ari, details, s.initiator_call)

        assert_that(destination.ari_endpoint(), equal_to(interface))

    def test_ari_endpoint_sccp_with_contact(self):
        interface = 'sccp/foobar'
        details = {'interface': interface, 'line_id': 42, 'contact': 'invalid'}
        destination = InterfaceDestination(self.ari, details, s.initiator_call)

        assert_that(destination.ari_endpoint(), equal_to(interface))

    def test_ari_endpoint_sip_no_contact(self):
        interface = 'pjsip/foobar'
        details = {'interface': interface, 'line_id': 42}
        destination = InterfaceDestination(self.ari, details, s.initiator_call)

        assert_that(destination.ari_endpoint(), equal_to(interface))

    def test_ari_endpoint_sip_contact_uri(self):
        contact_uri = 'PJSIP/ycetqvtr/sip:qthehhsk@127.0.0.1:40494;transport=ws'
        details = {
            'contact': contact_uri,
            'interface': 'pjsip/ycetqvtr',
            'line_id': 18,
        }
        destination = InterfaceDestination(self.ari, details, s.initiator_call)

        assert_that(destination.ari_endpoint(), equal_to(contact_uri))

    def test_ari_endpoint_sip_contact_name(self):
        contact_list = 'PJSIP/ycetqvtr/sip:osm5ohqg@127.0.0.1:54748;transport=ws&PJSIP/ycetqvtr/sip:lg12k0c1@127.0.0.1:54800;transport=ws&PJSIP/ycetqvtr/sip:947ia8sg@127.0.0.1:45270;transport=ws'
        self.ari.channels.getChannelVar.return_value = {'value': contact_list}
        details = {
            'contact': 'lg12k0c1',
            'interface': 'pjsip/ycetqvtr',
            'line_id': 18,
        }
        destination = InterfaceDestination(self.ari, details, s.initiator_call)

        self.ari.channels.getChannelVar.assert_called_once_with(
            channelId=s.initiator_call,
            variable='PJSIP_DIAL_CONTACTS(ycetqvtr)',
        )
        assert_that(
            destination.ari_endpoint(),
            equal_to('PJSIP/ycetqvtr/sip:lg12k0c1@127.0.0.1:54800;transport=ws'),
        )
