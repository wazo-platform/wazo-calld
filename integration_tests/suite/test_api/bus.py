# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import json
import uuid

from kombu import Connection
from kombu import Consumer
from kombu import Producer
from kombu import Queue
from kombu.exceptions import TimeoutError

from .constants import BUS_QUEUE_NAME
from .constants import BUS_URL
from .constants import BUS_EXCHANGE_XIVO


class BusClient(object):

    @classmethod
    def is_up(cls):
        try:
            with Connection(BUS_URL) as connection:
                producer = Producer(connection, exchange=BUS_EXCHANGE_XIVO, auto_declare=True)
                producer.publish('', routing_key='test')
        except IOError:
            return False
        else:
            return True

    @classmethod
    def accumulator(cls, routing_key, exchange=BUS_EXCHANGE_XIVO):
        queue_name = str(uuid.uuid4())
        with Connection(BUS_URL) as conn:
            queue = Queue(name=queue_name, exchange=exchange, routing_key=routing_key, channel=conn.channel())
            queue.declare()
            queue.purge()
            accumulator = BusMessageAccumulator(queue)
        return accumulator

    @classmethod
    def listen_events(cls, routing_key, exchange=BUS_EXCHANGE_XIVO):
        with Connection(BUS_URL) as conn:
            queue = Queue(BUS_QUEUE_NAME, exchange=exchange, routing_key=routing_key, channel=conn.channel())
            queue.declare()
            queue.purge()
            cls.bus_queue = queue

    @classmethod
    def events(cls):
        events = []

        def on_event(body, message):
            # events are already decoded, thanks to the content-type
            events.append(body)
            message.ack()

        cls._drain_events(on_event=on_event)

        return events

    @classmethod
    def _drain_events(cls, on_event):
        if not hasattr(cls, 'bus_queue'):
            raise Exception('You must listen for events before consuming them')
        with Connection(BUS_URL) as conn:
            with Consumer(conn, cls.bus_queue, callbacks=[on_event]):
                try:
                    while True:
                        conn.drain_events(timeout=0.5)
                except TimeoutError:
                    pass

    @classmethod
    def send_event(cls, event, routing_key):
        with Connection(BUS_URL) as connection:
            producer = Producer(connection, exchange=BUS_EXCHANGE_XIVO, auto_declare=True)
            producer.publish(json.dumps(event), routing_key=routing_key, content_type='application/json')

    @classmethod
    def send_ami_newchannel_event(cls, channel_id):
        cls.send_event({
            'data': {
                'Event': 'Newchannel',
                'Uniqueid': channel_id,
            }
        }, 'ami.Newchannel')

    @classmethod
    def send_ami_newstate_event(cls, channel_id):
        cls.send_event({
            'data': {
                'Event': 'Newstate',
                'Uniqueid': channel_id,
            }
        }, 'ami.Newstate')

    @classmethod
    def send_ami_hangup_event(cls, channel_id):
        cls.send_event({
            'data': {
                'Event': 'Hangup',
                'Uniqueid': channel_id,
                'ChannelStateDesc': 'Up',
                'CallerIDName': 'my-caller-id-name',
                'CallerIDNum': 'my-caller-id-num',
            }
        }, 'ami.Hangup')

    @classmethod
    def send_ami_hangup_userevent(cls, channel_id):
        cls.send_event({
            'data': {
                'Event': 'UserEvent',
                'UserEvent': 'Hangup',
                'Uniqueid': channel_id,
                'ChannelStateDesc': 'Up',
                'CallerIDName': 'my-caller-id-name',
                'CallerIDNum': 'my-caller-id-num',
                'ConnectedLineName': 'peer-name',
                'ConnectedLineNum': 'peer-num',
                'XIVO_USERUUID': 'my-uuid',
            }
        }, 'ami.UserEvent')


class BusMessageAccumulator(object):

    def __init__(self, queue):
        self._queue = queue
        self._events = []

    def _on_event(self, body, message):
        # events are already decoded, thanks to the content-type
        self._events.append(body)
        message.ack()

    def accumulate(self):
        with Connection(BUS_URL) as conn:
            with Consumer(conn, self._queue, callbacks=[self._on_event]):
                try:
                    while True:
                        conn.drain_events(timeout=0.5)
                except TimeoutError:
                    pass

        return self._events
