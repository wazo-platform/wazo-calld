# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import json
import logging

from kombu.mixins import ConsumerMixin
from kombu import Connection
from kombu import Exchange
from kombu import Queue

logger = logging.getLogger(__name__)


class CoreBus(ConsumerMixin):

    def __init__(self, config):
        self.config = config
        bus_url = 'amqp://{username}:{password}@{host}:{port}//'.format(**config)
        self.connection = Connection(bus_url)
        self.exchange = Exchange(config['exchange_name'], type=config['exchange_type'])
        self.ami_queue = Queue(exchange=self.exchange, routing_key='ami.*', exclusive=True)

    def get_consumers(self, Consumer, channel):
        return [Consumer(queues=self.ami_queue, callbacks=[self.on_ami_event])]

    def on_ami_event(self, body, message):
        body = json.loads(body)['data']
        if body['Event'] not in ('VarSet', 'Newexten'):
            logger.debug(body['Event'])
        if body['Event'] in ('OriginateResponse', 'Newchannel', 'NewConnectedLine', 'DialBegin'):
            logger.debug(body)
        message.ack()
