# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import json
import kombu
import logging
import Queue

from collections import defaultdict
from kombu import Connection
from kombu import Exchange
from kombu import Producer
from kombu.mixins import ConsumerMixin

from xivo_bus import Marshaler
from xivo_bus import Publisher


logger = logging.getLogger(__name__)


class CoreBusPublisher(object):

    def __init__(self, global_config):
        self.config = global_config['bus']
        self._queue = Queue.Queue()
        self._running = False
        self._should_stop = False
        self._uuid = global_config['uuid']
        self._bus_publisher = None

    def run(self):
        logger.info("Running AMQP publisher")

        self._running = True
        while not self._should_stop:
            try:
                message = self._queue.get(timeout=0.1)
                self._send_message(message)
            except Queue.Empty:
                pass
        self._running = False
        self._should_stop = False

    def _send_message(self, message):
        if self._bus_publisher is None:
            self._bus_publisher = self._make_publisher()

        self._bus_publisher.publish(message)

    def _make_publisher(self):
        bus_url = 'amqp://{username}:{password}@{host}:{port}//'.format(**self.config)
        bus_connection = Connection(bus_url)
        bus_exchange = Exchange(self.config['exchange_name'], type=self.config['exchange_type'])
        bus_producer = Producer(bus_connection, exchange=bus_exchange, auto_declare=True)
        bus_marshaler = Marshaler(self._uuid)
        return Publisher(bus_producer, bus_marshaler)

    def publish(self, event):
        self._queue.put(event)

    def stop(self):
        if self._running:
            self._should_stop = True


class CoreBusConsumer(ConsumerMixin):
    _KEY = 'ami.*'

    def __init__(self, global_config):
        self._bus_url = 'amqp://{username}:{password}@{host}:{port}//'.format(**global_config['bus'])
        self._callbacks = defaultdict(list)
        exchange = Exchange(global_config['bus']['exchange_name'],
                            type=global_config['bus']['exchange_type'])
        self._queue = kombu.Queue(exchange=exchange, routing_key=self._KEY, exclusive=True)

    def run(self):
        logger.info("Running AMQP consumer")
        with Connection(self._bus_url) as connection:
            self.connection = connection
            super(CoreBusConsumer, self).run()

    def get_consumers(self, Consumer, channel):
        return [
            Consumer(self._queue, callbacks=[self._on_bus_message]),
        ]

    def on_ami_event(self, event_type, callback):
        self._callbacks[event_type].append(callback)

    def _on_bus_message(self, body, message):
        msg = json.loads(body)
        event = msg['data']
        event_type = event['Event']
        for callback in self._callbacks[event_type]:
            try:
                callback(event)
            except Exception as e:
                logger.exception(e)
        message.ack()
