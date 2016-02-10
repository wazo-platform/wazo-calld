# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from kombu import Connection
from kombu import Exchange
from kombu import Producer

from xivo_bus import CollectdMarshaler
from xivo_bus import Publisher
from xivo_bus import PublishingQueue

logger = logging.getLogger(__name__)


class CoreCollectd(object):

    def __init__(self, global_config):
        self.config = dict(global_config['bus'])
        self.config.update(global_config['collectd'])
        self._uuid = global_config['uuid']
        self._publisher = PublishingQueue(self._make_publisher)

    def run(self):
        logger.info("Running AMQP publisher")

        self._publisher.run()

    def _make_publisher(self):
        bus_url = 'amqp://{username}:{password}@{host}:{port}//'.format(**self.config)
        bus_connection = Connection(bus_url)
        bus_exchange = Exchange(self.config['exchange_name'], type=self.config['exchange_type'])
        bus_producer = Producer(bus_connection, exchange=bus_exchange, auto_declare=False)
        bus_marshaler = CollectdMarshaler(self._uuid)
        return Publisher(bus_producer, bus_marshaler)

    def publish(self, event):
        self._publisher.publish(event)

    def stop(self):
        self._publisher.stop()
