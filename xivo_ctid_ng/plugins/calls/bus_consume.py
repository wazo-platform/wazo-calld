# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from requests.exceptions import HTTPError
from xivo_bus.resources.calls.event import CreateCallEvent
from xivo_bus.resources.calls.event import EndCallEvent
from xivo_bus.resources.calls.event import UpdateCallEvent

from xivo_ctid_ng.core.ari_ import not_found


logger = logging.getLogger(__name__)


class CallsBusEventHandler(object):

    def __init__(self, ari, bus_publisher, services):
        self.ari = ari
        self.bus_publisher = bus_publisher
        self.services = services

    def subscribe(self, bus_consumer):
        bus_consumer.on_ami_event('Newchannel', self._channel_created)
        bus_consumer.on_ami_event('Newstate', self._channel_updated)
        bus_consumer.on_ami_event('Hangup', self._channel_hung_up)

    def _channel_created(self, event):
        channel_id = event['Uniqueid']
        logger.debug('Relaying to bus: channel %s created', channel_id)
        channel = self.ari.channels.get(channelId=channel_id)
        call = self.services.make_call_from_channel(self.ari, channel)
        bus_event = CreateCallEvent(call.to_dict())
        self.bus_publisher.publish(bus_event)

    def _channel_updated(self, event):
        channel_id = event['Uniqueid']
        logger.debug('Relaying to bus: channel %s updated', channel_id)
        try:
            channel = self.ari.channels.get(channelId=channel_id)
        except HTTPError as e:
            if not_found(e):
                return
            raise
        call = self.services.make_call_from_channel(self.ari, channel)
        bus_event = UpdateCallEvent(call.to_dict())
        self.bus_publisher.publish(bus_event)

    def _channel_hung_up(self, event):
        channel_id = event['Uniqueid']
        logger.debug('Relaying to bus: channel %s ended', channel_id)
        call = self.services.make_call_from_ami_event(event)
        bus_event = EndCallEvent(call.to_dict())
        self.bus_publisher.publish(bus_event)
