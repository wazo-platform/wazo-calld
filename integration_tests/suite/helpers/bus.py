# Copyright 2015-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import json

from kombu import Connection
from kombu import Consumer
from kombu import Exchange
from kombu import Producer
from kombu import Queue
from kombu.exceptions import TimeoutError
from xivo_test_helpers import bus as bus_helper

from .constants import BUS_QUEUE_NAME
from .constants import BUS_EXCHANGE_HEADERS


class BusClient(bus_helper.BusClient):

    def listen_events(self, routing_key, exchange):
        with Connection(self._url) as conn:
            queue = Queue(BUS_QUEUE_NAME, exchange=exchange, routing_key=routing_key, channel=conn.channel())
            queue.declare()
            queue.purge()
            self.bus_queue = queue

    def events(self):
        events = []

        def on_event(body, message):
            # events are already decoded, thanks to the content-type
            events.append(body)
            message.ack()

        self._drain_events(on_event=on_event)

        return events

    def _drain_events(self, on_event):
        if not hasattr(self, 'bus_queue'):
            raise Exception('You must listen for events before consuming them')
        with Connection(self._url) as conn:
            with Consumer(conn, self.bus_queue, callbacks=[on_event]):
                try:
                    while True:
                        conn.drain_events(timeout=0.5)
                except TimeoutError:
                    pass

    def bind_exchanges(self, upstream_exchange_name, downstream_exchange_name):
        with Connection(self._url) as connection:
            upstream_exchange = Exchange(
                upstream_exchange_name,
                type='topic',
                auto_delete=False,
                durable=False,
                delivery_mode='persistent',
            )
            exchange = Exchange(
                downstream_exchange_name,
                type='headers',
                auto_delete=False,
                durable=False,
                delivery_mode='persistent',
            )

            upstream_exchange.bind(connection).declare()
            exchange = exchange.bind(connection)
            exchange.declare()
            exchange.bind_to(upstream_exchange, routing_key='#')

    def send_event(self, event):
        with Connection(self._url) as connection:
            producer = Producer(connection, exchange=BUS_EXCHANGE_HEADERS, auto_declare=True)
            producer.publish(json.dumps(event), headers={'name': event['name']}, content_type='application/json')

    def send_ami_newchannel_event(self, channel_id, channel=None):
        self.send_event({
            'name': 'Newchannel',
            'data': {
                'Event': 'Newchannel',
                'Uniqueid': channel_id,
                'Channel': channel or 'PJSIP/abcdef-00000001',
            }
        })

    def send_ami_newstate_event(self, channel_id, state='Up'):
        self.send_event({
            'name': 'Newstate',
            'data': {
                'Event': 'Newstate',
                'Uniqueid': channel_id,
                'ChannelStateDesc': state,
            }
        })

    def send_ami_hold_event(self, channel_id):
        self.send_event({
            'name': 'Hold',
            'data': {
                'Event': 'Hold',
                'Uniqueid': channel_id,
            }
        })

    def send_ami_unhold_event(self, channel_id):
        self.send_event({
            'name': 'Unhold',
            'data': {
                'Event': 'Unhold',
                'Uniqueid': channel_id,
            },
        })

    def send_ami_hangup_event(self, channel_id, base_exten=None, sip_call_id=None, channel=None):
        self.send_event({
            'name': 'Hangup',
            'data': {
                'Event': 'Hangup',
                'Uniqueid': channel_id,
                'Channel': channel or 'PJSIP/abcdef-00000001',
                'ChannelStateDesc': 'Up',
                'CallerIDName': 'my-caller-id-name',
                'CallerIDNum': 'my-caller-id-num',
                'ConnectedLineName': 'peer-name',
                'ConnectedLineNum': 'peer-num',
                'ChanVariable': {
                    'XIVO_USERUUID': 'my-uuid',
                    'XIVO_BASE_EXTEN': base_exten if base_exten else '*10',
                    'WAZO_SIP_CALL_ID': sip_call_id,
                },
            },
        })

    def send_ami_peerstatus_event(self, channel_type, peer, status):
        self.send_event({
            'name': 'PeerStatus',
            'data': {
                'Event': 'PeerStatus',
                'Privilege': 'system,all',
                'ChannelType': channel_type,
                'Peer': peer,
                'PeerStatus': status,
            },
        })

    def send_ami_registry_event(self, channel_type, domain, status, username):
        self.send_event({
            'name': 'Registry',
            'data': {
                'ChannelType': channel_type,
                'Domain': domain,
                'Event': 'Registry',
                'Privilege': 'system,all',
                'Status': status,
                'Username': username,
            },
        })

    def send_ami_dtmf_end_digit(self, channel_id, digit):
        self.send_event({
            'data': {
                'Event': 'DTMFEnd',
                'Uniqueid': channel_id,
                'Digit': digit,
            },
        })

    def send_moh_created_event(self, moh_uuid):
        self.send_event({
            'name': 'moh_created',
            'data': {
                'uuid': moh_uuid,
                'name': 'default',
            },
        })

    def send_moh_deleted_event(self, moh_uuid):
        self.send_event({
            'name': 'moh_deleted',
            'data': {
                'uuid': moh_uuid,
                'name': 'default',
            },
        })

    def send_application_created_event(self, application_uuid, destination=None):
        payload = {
            'name': 'application_created',
            'data': {
                'uuid': application_uuid,
                'name': 'test-app-name',
                'destination': destination,
                'destination_options': {},
            },
        }
        if destination:
            payload['data']['destination_options'] = {
                'type': 'holding',
                'music_on_hold': None,
                'answer': False,
            }
        self.send_event(payload)

    def send_application_edited_event(self, application_uuid, destination=None):
        payload = {
            'name': 'application_edited',
            'data': {
                'uuid': application_uuid,
                'name': 'test-app-name',
                'destination': destination,
                'destination_options': {},
            },
        }
        if destination:
            payload['data']['destination_options'] = {
                'type': 'holding',
                'music_on_hold': None,
                'answer': False,
            }
        self.send_event(payload)

    def send_application_deleted_event(self, application_uuid):
        payload = {
            'name': 'application_deleted',
            'data': {
                'uuid': application_uuid,
                'name': 'test-app-name',
                'destination': None,
                'destination_options': {},
            },
        }
        self.send_event(payload)

    def send_trunk_endpoint_associated_event(self, trunk_id, endpoint_id):
        payload = {
            'name': 'trunk_endpoint_associated',
            'data': {'trunk_id': trunk_id, 'endpoint_id': endpoint_id},
        }
        self.send_event(payload)
