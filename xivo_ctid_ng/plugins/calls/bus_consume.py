# -*- coding: utf-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from ari.exceptions import ARINotFound
from xivo_bus.collectd.channels import ChannelCreatedCollectdEvent
from xivo_bus.collectd.channels import ChannelEndedCollectdEvent
from xivo_bus.resources.calls.hold import CallOnHoldEvent
from xivo_bus.resources.calls.hold import CallResumeEvent
from xivo_bus.resources.common.event import ArbitraryEvent

from xivo_ctid_ng.helpers import ami
from xivo_ctid_ng.helpers.ari_ import Channel

from .schema import call_schema

logger = logging.getLogger(__name__)


class CallsBusEventHandler(object):

    def __init__(self, ami, ari, collectd, bus_publisher, services, xivo_uuid):
        self.ami = ami
        self.ari = ari
        self.collectd = collectd
        self.bus_publisher = bus_publisher
        self.services = services
        self.xivo_uuid = xivo_uuid

    def subscribe(self, bus_consumer):
        bus_consumer.on_ami_event('Newchannel', self._relay_channel_created)
        bus_consumer.on_ami_event('Newchannel', self._collectd_channel_created)
        bus_consumer.on_ami_event('Newstate', self._relay_channel_updated)
        bus_consumer.on_ami_event('NewConnectedLine', self._relay_channel_updated)
        bus_consumer.on_ami_event('Hold', self._channel_hold)
        bus_consumer.on_ami_event('Unhold', self._channel_unhold)
        bus_consumer.on_ami_event('Hangup', self._relay_channel_hung_up)
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
        bus_event = ArbitraryEvent(
            name='call_created',
            body=call_schema.dump(call).data,
            required_acl='events.calls.{}'.format(call.user_uuid)
        )
        bus_event.routing_key = 'calls.call.created'
        self.bus_publisher.publish(bus_event, headers={'user_uuid:{uuid}'.format(uuid=call.user_uuid): True})

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
        bus_event = ArbitraryEvent(
            name='call_updated',
            body=call_schema.dump(call).data,
            required_acl='events.calls.{}'.format(call.user_uuid)
        )
        bus_event.routing_key = 'calls.call.updated'
        self.bus_publisher.publish(bus_event, headers={'user_uuid:{uuid}'.format(uuid=call.user_uuid): True})

    def _relay_channel_hung_up(self, event):
        channel_id = event['Uniqueid']
        logger.debug('Relaying to bus: channel %s ended', channel_id)
        call = self.services.make_call_from_ami_event(event)
        bus_event = ArbitraryEvent(
            name='call_ended',
            body=call_schema.dump(call).data,
            required_acl='events.calls.{}'.format(call.user_uuid)
        )
        bus_event.routing_key = 'calls.call.ended'
        self.bus_publisher.publish(bus_event, headers={'user_uuid:{uuid}'.format(uuid=call.user_uuid): True})

    def _collectd_channel_ended(self, event):
        channel_id = event['Uniqueid']
        logger.debug('sending stat for channel ended %s', channel_id)
        self.collectd.publish(ChannelEndedCollectdEvent())

    def _channel_hold(self, event):
        channel_id = event['Uniqueid']
        logger.debug('marking channel %s on hold', channel_id)
        ami.set_variable_ami(self.ami, channel_id, 'XIVO_ON_HOLD', '1')

        user_uuid = Channel(channel_id, self.ari).user()
        bus_msg = CallOnHoldEvent(channel_id, user_uuid)
        self.bus_publisher.publish(bus_msg, headers={'user_uuid:{uuid}'.format(uuid=user_uuid): True})

    def _channel_unhold(self, event):
        channel_id = event['Uniqueid']
        logger.debug('marking channel %s not on hold', channel_id)
        ami.unset_variable_ami(self.ami, channel_id, 'XIVO_ON_HOLD')

        user_uuid = Channel(channel_id, self.ari).user()
        bus_msg = CallResumeEvent(channel_id, user_uuid)
        self.bus_publisher.publish(bus_msg, headers={'user_uuid:{uuid}'.format(uuid=user_uuid): True})
