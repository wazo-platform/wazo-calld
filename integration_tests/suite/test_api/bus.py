# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import json

from kombu import Connection
from kombu import Consumer
from kombu import Exchange
from kombu import Queue
from kombu.exceptions import TimeoutError

from .constants import BUS_EXCHANGE_NAME
from .constants import BUS_EXCHANGE_TYPE
from .constants import BUS_URL
from .constants import BUS_QUEUE_NAME


class BusClient(object):

    @classmethod
    def listen_events(cls, routing_key):
        exchange = Exchange(BUS_EXCHANGE_NAME, type=BUS_EXCHANGE_TYPE)
        with Connection(BUS_URL) as conn:
            queue = Queue(BUS_QUEUE_NAME, exchange=exchange, routing_key=routing_key, channel=conn.channel())
            queue.declare()
            queue.purge()
            cls.bus_queue = queue

    @classmethod
    def events(cls):
        events = []

        def on_event(body, message):
            events.append(json.loads(body))
            message.ack()

        with Connection(BUS_URL) as conn:
            with Consumer(conn, cls.bus_queue, callbacks=[on_event]):
                try:
                    conn.drain_events(timeout=0.5)
                except TimeoutError:
                    pass

        return events
