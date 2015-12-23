# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from kombu import Connection
from kombu import Exchange
from kombu import Producer
from Queue import Queue
from Queue import Empty

from xivo_bus import Marshaler
from xivo_bus import Publisher

logger = logging.getLogger(__name__)


class CoreBus(object):

    def __init__(self, global_config):
        self.config = global_config['bus']
        self._queue = Queue()
        self._running = False
        self._should_stop = False
        self._uuid = global_config['uuid']
        self._bus_publisher = None

    def run(self):
        logger.info("Running AMQP interfaces publisher")

        self._running = True
        while not self._should_stop:
            try:
                message = self._queue.get(timeout=0.1)
                self._send_message(message)
            except Empty:
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
