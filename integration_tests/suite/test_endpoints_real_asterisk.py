# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import time

from hamcrest import assert_that, has_entries, has_item, has_items, is_in, not_
from wazo_test_helpers import until

from .helpers.amid import AmidClient
from .helpers.constants import CALLD_SERVICE_TOKEN, XIVO_UUID
from .helpers.real_asterisk import RealAsteriskIntegrationTest

TENANT = 'ffffffff-ffff-4c1c-ad1c-ffffffffff01'
CLIENT_URI = 'sip:line-abc@127.0.0.1:5060'


def peer_status(endpoint, status):
    def matches(event):
        data = event['data']
        return data['Peer'] == f'PJSIP/{endpoint}' and data['PeerStatus'] == status

    return matches


def registry(client_uri, status):
    def matches(event):
        data = event['data']
        return data['Username'] == client_uri and data['Status'] == status

    return matches


class TestEndpointIdentityFromAsterisk(RealAsteriskIntegrationTest):
    asset = 'real_asterisk_endpoints'

    def setUp(self):
        super().setUp()
        self.confd.reset()

    def asterisk(self, command):
        self.docker_exec(['asterisk', '-rx', command], 'ari')

    def status_events(self, accumulator, endpoint_id, registered):
        return [
            event
            for event in accumulator.accumulate(with_headers=True)
            if event['message']['data']['id'] == endpoint_id
            and event['message']['data']['registered'] is registered
        ]

    def wait_for_status(self, accumulator, endpoint_id, registered, ami_events, ami):
        # The delay of calld is measured from the AMI event on the bus to the
        # status event, both seen by this one poller; Asterisk's own delay to
        # register is not calld's.
        seen = {}

        def published():
            now = time.monotonic()
            if 'ami' not in seen and any(ami(e) for e in ami_events.accumulate()):
                seen['ami'] = now
            events = self.status_events(accumulator, endpoint_id, registered)
            assert events, f'no status event for {endpoint_id} {registered}'
            seen['status'] = now
            return events[0]

        event = until.return_(published, timeout=15, interval=0.02)
        delay = seen['status'] - seen.get('ami', seen['status'])
        print(
            f'{event["message"]["name"]} id={endpoint_id} registered={registered}:'
            f' {delay:.3f} s after the AMI event'
        )
        assert delay < 1, delay
        return event

    def assert_no_line_or_trunk_list_from_confd(self):
        paths = [request['path'] for request in self.confd.requests()['requests']]
        assert_that(paths, not_(has_item(is_in(['/1.1/lines', '/1.1/trunks']))))

    def test_ari_answers_the_wazo_identity_of_each_endpoint(self):
        for name, variable, value in [
            ('line-abc', 'WAZO_LINE_ID', '42'),
            ('trunk-reg', 'WAZO_TRUNK_ID', '7'),
        ]:
            started = time.monotonic()
            tuples = self.ari.asterisk.getObject(
                configClass='res_pjsip', objectType='endpoint', id=name
            )
            print(f'ARI getObject {name}: {(time.monotonic() - started) * 1000:.2f} ms')
            assert_that(
                tuples,
                has_items(
                    has_entries(attribute=variable, value=value),
                    has_entries(attribute='__WAZO_TENANT_UUID', value=TENANT),
                ),
            )

    def test_the_outbound_registrations_name_their_client_uri_and_endpoint(self):
        amid = AmidClient(
            '127.0.0.1',
            self.service_port(9491, 'amid'),
            prefix=None,
            https=False,
            token=str(CALLD_SERVICE_TOKEN),
        )

        registrations = amid.action('PJSIPShowRegistrationsOutbound')

        assert_that(
            registrations,
            has_item(
                has_entries(
                    Event='OutboundRegistrationDetail',
                    ClientUri=CLIENT_URI,
                    Endpoint='trunk-reg',
                )
            ),
        )

    def test_peer_status_publishes_the_line_and_trunk_from_asterisk(self):
        lines = self.bus.accumulator(headers={'name': 'line_status_updated'})
        trunks = self.bus.accumulator(headers={'name': 'trunk_status_updated'})
        peer_statuses = self.bus.accumulator(headers={'name': 'PeerStatus'})
        # the endpoints are unregistered first, so that each command is a change
        self.asterisk('pjsip send unregister trunk-reg')
        self.asterisk('pjsip send unregister to-trunk-peer')
        for registered in (True, False):
            command = 'register' if registered else 'unregister'
            self.asterisk(f'pjsip send {command} trunk-reg')
            self.asterisk(f'pjsip send {command} to-trunk-peer')

            status = 'Reachable' if registered else 'Unreachable'
            line = self.wait_for_status(
                lines, 42, registered, peer_statuses, peer_status('line-abc', status)
            )
            trunk = self.wait_for_status(
                trunks, 8, registered, peer_statuses, peer_status('trunk-peer', status)
            )

            for event in (line, trunk):
                assert_that(
                    event,
                    has_entries(
                        headers=has_entries(tenant_uuid=TENANT),
                        message=has_entries(origin_uuid=XIVO_UUID),
                    ),
                )
        self.assert_no_line_or_trunk_list_from_confd()

    def test_registry_publishes_the_trunk_from_its_client_uri(self):
        trunks = self.bus.accumulator(headers={'name': 'trunk_status_updated'})
        registries = self.bus.accumulator(headers={'name': 'Registry'})

        self.asterisk('pjsip send unregister trunk-reg')
        for registered in (True, False):
            command = 'register' if registered else 'unregister'
            self.asterisk(f'pjsip send {command} trunk-reg')

            status = 'Registered' if registered else 'Unregistered'
            event = self.wait_for_status(
                trunks, 7, registered, registries, registry(CLIENT_URI, status)
            )

            assert_that(
                event,
                has_entries(
                    headers=has_entries(tenant_uuid=TENANT),
                    message=has_entries(
                        data=has_entries(technology='sip', name='trunk-reg')
                    ),
                ),
            )
        self.assert_no_line_or_trunk_list_from_confd()
