# -*- coding: utf-8 -*-
# Copyright (C) 2015 Avencall
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

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
