# Copyright 2015-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_bus.publisher import BusPublisher
from xivo_bus.resources.common.event import ServiceEvent

from .constants import SOME_STASIS_APP, VALID_TENANT, XIVO_UUID


class _StasisEvent(ServiceEvent):
    name = '{event_name}'
    routing_key_fmt = ''  # Blank since must be defined but using headers for routing

    def __init__(self, content):
        self.name = type(self).name.format(event_name=content['type'])
        super().__init__(content)


class StasisClient:

    def __init__(self, host, port):
        bus_config = {
            'username': 'guest',
            'password': 'guest',
            'host': host,
            'port': port,
            'exchange_name': 'wazo-headers',
            'exchange_type': 'headers',
        }
        self._publisher = BusPublisher(service_uuid=XIVO_UUID, **bus_config)

    def _send_stasis_event(self, body):
        headers = {
            'category': 'stasis',
            'name': body['type'],
            'application_name': body['application'],
        }

        event = _StasisEvent(body)

        self._publisher.publish(event, headers)

    def event_answer_connect(self, from_, new_call_id, stasis_app, stasis_app_instance):
        body = {
            "application": stasis_app,
            "args": [
                stasis_app_instance,
                "dialed_from",
                from_
            ],
            "channel": {
                "accountcode": "",
                "caller": {
                    "name": "my-name",
                    "number": "my-number"
                },
                "connected": {
                    "name": "",
                    "number": ""
                },
                "creationtime": "2015-12-16T15:13:59.526-0500",
                "dialplan": {
                    "context": "default",
                    "exten": "",
                    "priority": 1
                },
                "id": new_call_id,
                "language": "en_US",
                "name": "PJSIP/my-sip-00000020",
                "state": "Up"
            },
            "timestamp": "2015-12-16T15:14:04.269-0500",
            "type": "StasisStart"
        }
        return self._send_stasis_event(body)

    def event_hangup(self, channel_id):
        body = {
            "application": SOME_STASIS_APP,
            "channel": {
                "accountcode": "code",
                "caller": {
                    "name": "my-name",
                    "number": "my-number"
                },
                "connected": {
                    "name": "",
                    "number": ""
                },
                "creationtime": "2015-12-18T15:40:32.439-0500",
                "dialplan": {
                    "context": "default",
                    "exten": "my-exten",
                    "priority": 1
                },
                "id": channel_id,
                "language": "fr_FR",
                "name": "my-name",
                "state": "Ring"
            },
            "timestamp": "2015-12-18T15:40:39.073-0500",
            "type": "StasisEnd"
        }
        return self._send_stasis_event(body)

    def event_stasis_start(self, channel_id, stasis_app, stasis_app_instance, stasis_args=None):
        stasis_args = stasis_args or []
        body = {
            "application": stasis_app,
            "args": [stasis_app_instance] + stasis_args,
            "channel": {
                "accountcode": "code",
                "caller": {
                    "name": "my-name",
                    "number": "my-number"
                },
                "connected": {
                    "name": "",
                    "number": ""
                },
                "creationtime": "2016-02-04T14:25:00.007-0500",
                "dialplan": {
                    "context": "default",
                    "exten": "my-exten",
                    "priority": 1
                },
                "id": channel_id,
                "language": "fr_FR",
                "name": "my-name",
                "state": "Ring"
            },
            "timestamp": "2016-02-04T14:25:00.408-0500",
            "type": "StasisStart"
        }
        return self._send_stasis_event(body)

    def event_channel_destroyed(
        self,
        channel_id,
        stasis_app,
        line_id=None,
        cause=0,
        channel_direction='from-wazo',
        sip_call_id=None,
        creation_time=None,
        timestamp=None,
        connected_number='',
        answer_time=None,
    ):
        creation_time = creation_time or "2016-02-04T15:10:21.225-0500"
        timestamp = timestamp or "2016-02-04T15:10:22.548-0500"
        body = {
            "application": stasis_app,
            "cause": cause,
            "cause_txt": "Unknown",
            "channel": {
                "accountcode": "code",
                "caller": {
                    "name": "my-name",
                    "number": "my-number"
                },
                "connected": {
                    "name": "",
                    "number": connected_number
                },
                "channelvars": {
                    'WAZO_ANSWER_TIME': answer_time,
                    'WAZO_CHANNEL_DIRECTION': channel_direction,
                    "WAZO_LINE_ID": line_id,
                    'WAZO_SIP_CALL_ID': sip_call_id,
                    'WAZO_TENANT_UUID': VALID_TENANT,
                },
                "creationtime": creation_time,
                "dialplan": {
                    "context": "default",
                    "exten": "my-exten",
                    "priority": 1
                },
                "id": channel_id,
                "language": "fr_FR",
                "name": "my-name",
                "state": "Down"
            },
            "timestamp": timestamp,
            "type": "ChannelDestroyed"
        }
        return self._send_stasis_event(body)
