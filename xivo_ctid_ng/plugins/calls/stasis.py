# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo_bus.resources.calls.event import CreateCallEvent
from xivo_bus.resources.calls.event import UpdateCallEvent
from xivo_bus.resources.calls.event import EndCallEvent

logger = logging.getLogger(__name__)


class CallsStasis(object):

    def __init__(self, ari_client, bus, services):
        self.ari = ari_client
        self.bus = bus
        self.services = services

    def subscribe(self):
        self.ari.on_channel_event('StasisStart', self.bridge_connect_user)
        self.ari.on_channel_event('StasisStart', self.relay_channel_created)
        self.ari.on_channel_event('ChannelStateChange', self.relay_channel_updated)
        self.ari.on_channel_event('StasisEnd', self.relay_channel_ended)

    def bridge_connect_user(self, event_objects, event):
        if not event.get('args'):
            return

        channel = event_objects['channel']
        if event['args'][0] == 'dialed_from':
            originator_channel_id = event['args'][1]
            originator_channel = self.ari.channels.get(channelId=originator_channel_id)
            channel.answer()
            originator_channel.answer()
            this_channel_id = channel.id
            bridge = self.ari.bridges.create(type='mixing')
            bridge.addChannel(channel=originator_channel_id)
            bridge.addChannel(channel=this_channel_id)

    def relay_channel_created(self, event_objects, event):
        logger.debug('Relaying to bus: channel %s created', event_objects['channel'].id)
        call = self.services.make_call_from_channel(self.ari, event_objects['channel'])
        bus_event = CreateCallEvent(call.to_dict())
        self.bus.publish(bus_event)

    def relay_channel_updated(self, channel, event):
        logger.debug('Relaying to bus: channel %s updated', channel.id)
        call = self.services.make_call_from_channel(self.ari, channel)
        bus_event = UpdateCallEvent(call.to_dict())
        self.bus.publish(bus_event)

    def relay_channel_ended(self, channel, event):
        logger.debug('Relaying to bus: channel %s ended', channel.id)
        call = self.services.make_call_from_channel(self.ari, channel)
        bus_event = EndCallEvent(call.to_dict())
        self.bus.publish(bus_event)
