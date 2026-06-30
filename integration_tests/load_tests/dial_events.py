# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Publish synthetic ``dial`` StasisStart events for the dial_mobile app.

Mirrors integration_tests/suite/helpers/stasis.py but adds the
``channel.channelvars['CHANNEL(linkedid)']`` field that
``DialMobileStasis.stasis_start`` reads, and builds ``args=['dial', <aor>]`` as
expected by the dial action. Each published event makes dial_mobile spawn a new
``_PollingContactDialer`` thread referencing the given (real) channel id.
"""
from __future__ import annotations

from wazo_bus.publisher import BusPublisher
from wazo_bus.resources.common.event import ServiceEvent

# Mirrors integration_tests/suite/helpers/constants.py
XIVO_UUID = '08c56466-8f29-45c7-9856-92bf1ba89b92'


class _StasisEvent(ServiceEvent):
    name = '{event_name}'
    routing_key_fmt = ''  # Blank but required; routing uses headers

    def __init__(self, content: dict):
        self.name = type(self).name.format(event_name=content['type'])
        super().__init__(content)


class DialMobileEventPublisher:
    def __init__(self, host: str, port: int):
        self._publisher = BusPublisher(
            service_uuid=XIVO_UUID,
            username='guest',
            password='guest',
            host=host,
            port=port,
            exchange_name='wazo-headers',
            exchange_type='headers',
        )

    def publish_dial(self, channel_id: str, aor: str) -> None:
        body = {
            'application': 'dial_mobile',
            'args': ['dial', aor],
            'channel': {
                'accountcode': '',
                'caller': {'name': 'load-test', 'number': '1000'},
                'connected': {'name': '', 'number': ''},
                'channelvars': {'CHANNEL(linkedid)': channel_id},
                'creationtime': '2026-01-01T00:00:00.000-0500',
                'dialplan': {'context': 'default', 'exten': '', 'priority': 1},
                'id': channel_id,
                'language': 'en_US',
                'name': f'Test/load-{channel_id}',
                'state': 'Up',
            },
            'timestamp': '2026-01-01T00:00:00.000-0500',
            'type': 'StasisStart',
        }
        headers = {
            'category': 'stasis',
            'name': body['type'],
            'application_name': body['application'],
        }
        self._publisher.publish(_StasisEvent(body), headers)
