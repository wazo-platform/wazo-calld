# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from ari.exceptions import ARINotFound
from xivo_bus.collectd.channels import ChannelCreatedCollectdEvent
from xivo_bus.collectd.channels import ChannelEndedCollectdEvent
from xivo_bus.resources.calls.event import CreateCallEvent
from xivo_bus.resources.calls.event import EndCallEvent
from xivo_bus.resources.calls.event import UpdateCallEvent


logger = logging.getLogger(__name__)


class CallsBusEventHandler(object):

    def __init__(self, ari, collectd, bus_publisher, services, xivo_uuid):
        self.ari = ari
        self.collectd = collectd
        self.bus_publisher = bus_publisher
        self.services = services
        self.xivo_uuid = xivo_uuid

    def subscribe(self, bus_consumer):
        bus_consumer.on_ami_event('Newchannel', self._relay_channel_created)
        bus_consumer.on_ami_event('Newchannel', self._collectd_channel_created)
        bus_consumer.on_ami_event('Newstate', self._relay_channel_updated)
        bus_consumer.on_ami_userevent('Hangup', self._relay_channel_hung_up)
        bus_consumer.on_ami_event('Hangup', self._collectd_channel_ended)

    def _relay_channel_created(self, event):
        channel_id = event['Uniqueid']
        logger.debug('Relaying to bus: channel %s created', channel_id)
        try:
            channel = self.ari.channels.get(channelId=channel_id)
        except ARINotFound:
            logger.debug('channel %s not found', channel_id)
            return
        call = self.services.make_call_from_channel(self.ari, channel)
        bus_event = CreateCallEvent(call.to_dict())
        self.bus_publisher.publish(bus_event)

    def _collectd_channel_created(self, event):
        channel_id = event['Uniqueid']
        logger.debug('sending stat for new channel %s', channel_id)
        self.collectd.publish(ChannelCreatedCollectdEvent())

    def _relay_channel_updated(self, event):
        channel_id = event['Uniqueid']
        logger.debug('Relaying to bus: channel %s updated', channel_id)
        try:
            channel = self.ari.channels.get(channelId=channel_id)
        except ARINotFound:
            logger.debug('channel %s not found', channel_id)
            return
        call = self.services.make_call_from_channel(self.ari, channel)
        bus_event = UpdateCallEvent(call.to_dict())
        self.bus_publisher.publish(bus_event)

    def _relay_channel_hung_up(self, event):
        channel_id = event['Uniqueid']
        logger.debug('Relaying to bus: channel %s ended', channel_id)
        call = self.services.make_call_from_ami_event(event)
        bus_event = EndCallEvent(call.to_dict())
        self.bus_publisher.publish(bus_event)

    def _collectd_channel_ended(self, event):
        channel_id = event['Uniqueid']
        logger.debug('sending stat for channel ended %s', channel_id)
        self.collectd.publish(ChannelEndedCollectdEvent())
