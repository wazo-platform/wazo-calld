# Copyright 2015-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import json

from kombu import Connection
from kombu import Consumer
from kombu import Producer
from kombu import Queue
from kombu.exceptions import TimeoutError
from wazo_test_helpers import bus as bus_helper

from .constants import BUS_QUEUE_NAME
from .constants import BUS_EXCHANGE_WAZO
from .constants import VALID_TENANT


class BusClient(bus_helper.BusClient):

    def listen_events(self, routing_key, exchange=BUS_EXCHANGE_WAZO):
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

    def send_event(self, event, headers=None):
        with Connection(self._url) as connection:
            producer = Producer(connection, exchange=BUS_EXCHANGE_WAZO, auto_declare=True)
            producer.publish(
                json.dumps(event),
                headers=headers,
                content_type='application/json'
            )

    def send_ami_newchannel_event(self, channel_id, channel=None):
        self.send_event(
            {
                'data': {
                    'Event': 'Newchannel',
                    'Uniqueid': channel_id,
                    'Channel': channel or 'PJSIP/abcdef-00000001',
                }
            },
            headers={
                'name': 'Newchannel',
            },
        )

    def send_ami_newstate_event(self, channel_id, state='Up', channel=None):
        self.send_event(
            {
                'data': {
                    'Channel': channel or 'PJSIP/abcdef-00000001',
                    'Event': 'Newstate',
                    'Uniqueid': channel_id,
                    'ChannelStateDesc': state,
                }
            },
            headers={
                'name': 'Newstate',
            },
        )

    def send_ami_hold_event(self, channel_id):
        self.send_event(
            {
                'data': {
                    'Event': 'Hold',
                    'Uniqueid': channel_id,
                }
            },
            headers={
                'name': 'Hold',
            },
        )

    def send_ami_unhold_event(self, channel_id):
        self.send_event(
            {
                'data': {
                    'Event': 'Unhold',
                    'Uniqueid': channel_id,
                }
            },
            headers={
                'name': 'Unhold',
            },
        )

    def send_ami_hangup_event(self, channel_id, entry_exten=None, sip_call_id=None, channel=None, line_id=None):
        self.send_event(
            {
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
                        'WAZO_ENTRY_EXTEN': entry_exten if entry_exten else '*10',
                        'WAZO_SIP_CALL_ID': sip_call_id,
                        'WAZO_LINE_ID': line_id,
                    },
                }
            },
            headers={
                'name': 'Hangup',
            },
        )

    def send_ami_bridge_leave_event(self, channel_id, bridge_id, bridge_num_channels):
        self.send_event(
            {
                'data': {
                    'Event': 'BridgeLeave',
                    'Uniqueid': channel_id,
                    'BridgeUniqueid': bridge_id,
                    'BridgeNumChannels': bridge_num_channels,
                }
            },
            headers={
                'name': 'BridgeLeave',
            },
        )

    def send_ami_peerstatus_event(self, channel_type, peer, status):
        self.send_event(
            {
                'data': {
                    'Event': 'PeerStatus',
                    'Privilege': 'system,all',
                    'ChannelType': channel_type,
                    'Peer': peer,
                    'PeerStatus': status,
                },
            },
            headers={
                'name': 'PeerStatus',
            },
        )

    def send_ami_registry_event(self, channel_type, domain, status, username):
        self.send_event(
            {
                'data': {
                    'ChannelType': channel_type,
                    'Domain': domain,
                    'Event': 'Registry',
                    'Privilege': 'system,all',
                    'Status': status,
                    'Username': username,
                },
            },
            headers={
                'name': 'Registry',
            },
        )

    def send_ami_dtmf_end_digit(self, channel_id, digit):
        self.send_event(
            {
                'data': {
                    'Event': 'DTMFEnd',
                    'Uniqueid': channel_id,
                    'Digit': digit,
                },
            },
            headers={
                'name': 'DTMFEnd',
            },
        )

    def send_moh_created_event(self, moh_uuid):
        self.send_event(
            {
                'data': {
                    'uuid': moh_uuid,
                    'name': 'default',
                },
                'name': 'moh_created',
            },
            headers={
                'name': 'moh_created',
            },
        )

    def send_moh_deleted_event(self, moh_uuid):
        self.send_event(
            {
                'data': {
                    'uuid': moh_uuid,
                    'name': 'default',
                },
                'name': 'moh_deleted',
            },
            headers={
                'name': 'moh_deleted',
            },
        )

    def send_application_created_event(self, application_uuid, destination=None):
        payload = {
            'data': {
                'uuid': application_uuid,
                'tenant_uuid': VALID_TENANT,
                'name': 'test-app-name',
                'destination': destination,
                'destination_options': {},
            },
            'name': 'application_created',
        }
        if destination:
            payload['data']['destination_options'] = {
                'type': 'holding',
                'music_on_hold': None,
                'answer': False,
            }
        self.send_event(
            payload,
            headers={'name': 'application_created'},
        )

    def send_application_edited_event(self, application_uuid, destination=None):
        payload = {
            'data': {
                'uuid': application_uuid,
                'tenant_uuid': VALID_TENANT,
                'name': 'test-app-name',
                'destination': destination,
                'destination_options': {},
            },
            'name': 'application_edited',
        }
        if destination:
            payload['data']['destination_options'] = {
                'type': 'holding',
                'music_on_hold': None,
                'answer': False,
            }
        self.send_event(
            payload,
            headers={'name': 'application_edited'},
        )

    def send_application_deleted_event(self, application_uuid):
        payload = {
            'data': {
                'uuid': application_uuid,
                'tenant_uuid': VALID_TENANT,
                'name': 'test-app-name',
                'destination': None,
                'destination_options': {},
            },
            'name': 'application_deleted',
        }
        self.send_event(
            payload,
            headers={'name': 'application_deleted'},
        )

    def send_trunk_endpoint_associated_event(self, trunk_id, endpoint_id):
        payload = {
            'data': {'trunk_id': trunk_id, 'endpoint_id': endpoint_id},
            'name': 'trunk_endpoint_associated',
        }
        self.send_event(
            payload,
            headers={'name': 'trunk_endpoint_associated'},
        )

    def send_user_missed_call_userevent(self, user_uuid, reason, hangup_cause, conversation_id):
        self.send_event(
            {
                'data': {
                    'Event': 'UserEvent',
                    'UserEvent': 'user_missed_call',
                    'destination_user_uuid': user_uuid,
                    'reason': reason,
                    'hangup_cause': hangup_cause,
                    'caller_user_uuid': '',
                    'caller_id_name': '',
                    'caller_id_number': '',
                    'entry_exten': '',
                    'conversation_id': conversation_id,
                    'ChanVariable': {
                        'WAZO_TENANT_UUID': VALID_TENANT,
                    },
                },
            },
            headers={
                'name': 'UserEvent',
            },
        )

    def send_user_dnd_update(self, user_id, enabled):
        self.send_event(
            {
                'name': 'users_services_dnd_updated',
                'data': {'user_id': user_id, 'user_uuid': user_id, 'enabled': enabled},
            },
            headers={
                'name': 'users_services_dnd_updated',
            },
        )

    def send_meeting_deleted_event(self, meeting_uuid):
        payload = {
            'data': {
                'uuid': meeting_uuid,
                'name': 'test-meeting-name',
            },
            'name': 'meeting_deleted',
        }
        self.send_event(
            payload,
            headers={'name': 'meeting_deleted'},
        )

    def send_stasis_non_json_event(self):
        self.send_event('', headers={'category': 'stasis', 'name': 'StasisStart'})
