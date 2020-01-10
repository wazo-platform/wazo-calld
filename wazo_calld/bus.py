# Copyright 2015-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import kombu
import kombu.mixins
import logging

from xivo.pubsub import Pubsub
from xivo.status import Status
from xivo_bus import Marshaler
from xivo_bus import Publisher
from xivo_bus import PublishingQueue

logger = logging.getLogger(__name__)


class CoreBusPublisher:

    def __init__(self, global_config):
        self.config = global_config['bus']
        self._uuid = global_config['uuid']
        self._publisher = PublishingQueue(self._make_publisher)

    def run(self):
        logger.info("Running AMQP publisher")

        self._publisher.run()

    def _make_publisher(self):
        bus_url = 'amqp://{username}:{password}@{host}:{port}//'.format(**self.config)
        bus_connection = kombu.Connection(bus_url)
        bus_exchange = kombu.Exchange(self.config['publish_exchange_name'], type=self.config['publish_exchange_type'])
        bus_producer = kombu.Producer(bus_connection, exchange=bus_exchange, auto_declare=True)
        bus_marshaler = Marshaler(self._uuid)
        return Publisher(bus_producer, bus_marshaler)

    def publish(self, event, headers=None):
        logger.debug('Publishing event "%s": %s', event.name, event.marshal())
        self._publisher.publish(event, headers)

    def stop(self):
        self._publisher.stop()


class CoreBusConsumer(kombu.mixins.ConsumerMixin):

    def __init__(self, global_config):
        self._events_pubsub = Pubsub()

        self._bus_url = 'amqp://{username}:{password}@{host}:{port}//'.format(**global_config['bus'])
        self._exchange = kombu.Exchange(global_config['bus']['subscribe_exchange_name'],
                                        type=global_config['bus']['subscribe_exchange_type'])
        self._queue = kombu.Queue(exclusive=True)
        self._is_running = False

    def run(self):
        logger.info("Running AMQP consumer")
        with kombu.Connection(self._bus_url) as connection:
            self.connection = connection

            super().run()

    def get_consumers(self, Consumer, channel):
        return [
            Consumer(self._queue, callbacks=[self._on_bus_message])
        ]

    def on_connection_error(self, exc, interval):
        super().on_connection_error(exc, interval)
        self._is_running = False

    def on_connection_revived(self):
        super().on_connection_revived()
        self._is_running = True

    def is_running(self):
        return self._is_running

    def provide_status(self, status):
        status['bus_consumer']['status'] = Status.ok if self.is_running() else Status.fail

    def on_event(self, event_name, callback):
        logger.debug('Added callback on event "%s"', event_name)
        self._queue.bindings.add(
            kombu.binding(self._exchange, arguments={'x-match': 'all', 'name': event_name})
        )
        self._events_pubsub.subscribe(event_name, callback)

    def _on_bus_message(self, body, message):
        try:
            event = body['data']
            event_type = event['Event'] if self._is_ami_event(event) else body['name']
        except KeyError:
            logger.error('Invalid event message received: %s', body)
        else:
            self._events_pubsub.publish(event_type, event)
        finally:
            message.ack()

    def _is_ami_event(self, event):
        return 'Event' in event
