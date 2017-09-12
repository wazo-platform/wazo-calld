# -*- coding: utf-8 -*-
# Copyright 2015-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import kombu
import logging

from kombu import binding
from kombu import Connection
from kombu import Exchange
from kombu import Producer
from kombu.mixins import ConsumerMixin
from xivo.pubsub import Pubsub
from xivo_bus import Marshaler
from xivo_bus import Publisher
from xivo_bus import PublishingQueue

from .status import Status

logger = logging.getLogger(__name__)


class CoreBusPublisher(object):

    def __init__(self, global_config):
        self.config = global_config['bus']
        self._uuid = global_config['uuid']
        self._publisher = PublishingQueue(self._make_publisher)

    def run(self):
        logger.info("Running AMQP publisher")

        self._publisher.run()

    def _make_publisher(self):
        bus_url = 'amqp://{username}:{password}@{host}:{port}//'.format(**self.config)
        bus_connection = Connection(bus_url)
        bus_exchange = Exchange(self.config['exchange_name'], type=self.config['exchange_type'])
        bus_producer = Producer(bus_connection, exchange=bus_exchange, auto_declare=True)
        bus_marshaler = Marshaler(self._uuid)
        return Publisher(bus_producer, bus_marshaler)

    def publish(self, event, headers=None):
        logger.debug('Publishing event "%s": %s', event.name, event.marshal())
        self._publisher.publish(event, headers)

    def stop(self):
        self._publisher.stop()


class CoreBusConsumer(ConsumerMixin):

    def __init__(self, global_config):
        self._events_pubsub = Pubsub()
        self._userevent_pubsub = Pubsub()
        self._events_pubsub.subscribe('UserEvent',
                                      lambda message: self._userevent_pubsub.publish(message['UserEvent'], message))

        self._bus_url = 'amqp://{username}:{password}@{host}:{port}//'.format(**global_config['bus'])
        self._exchange = Exchange(global_config['bus']['exchange_name'],
                                  type=global_config['bus']['exchange_type'])
        self._queue = kombu.Queue(exclusive=True)
        self._is_running = False

    def run(self):
        logger.info("Running AMQP consumer")
        with Connection(self._bus_url) as connection:
            self.connection = connection

            super(CoreBusConsumer, self).run()

    def get_consumers(self, Consumer, channel):
        return [
            Consumer(self._queue, callbacks=[self._on_bus_message])
        ]

    def on_connection_error(self, exc, interval):
        super(CoreBusConsumer, self).on_connection_error(exc, interval)
        self._is_running = False

    def on_connection_revived(self):
        super(CoreBusConsumer, self).on_connection_revived()
        self._is_running = True

    def is_running(self):
        return self._is_running

    def provide_status(self, status):
        status['connections']['bus_consumer'] = Status.ok if self.is_running() else Status.fail

    def on_ami_event(self, event_type, callback):
        self._queue.bindings.add(binding(self._exchange, routing_key='ami.{}'.format(event_type)))
        self._events_pubsub.subscribe(event_type, callback)

    def on_ami_userevent(self, userevent_type, callback):
        self._queue.bindings.add(binding(self._exchange, routing_key='ami.UserEvent'))
        self._userevent_pubsub.subscribe(userevent_type, callback)

    def _on_bus_message(self, body, message):
        event = body['data']
        event_type = event['Event']
        self._events_pubsub.publish(event_type, event)
        message.ack()
