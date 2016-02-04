# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import datetime
import logging

from xivo_bus.collectd.calls.event import CallAbandonedCollectdEvent
from xivo_bus.collectd.calls.event import CallConnectCollectdEvent
from xivo_bus.collectd.calls.event import CallDurationCollectdEvent
from xivo_bus.collectd.calls.event import CallEndCollectdEvent
from xivo_bus.collectd.calls.event import CallStartCollectdEvent

logger = logging.getLogger(__name__)


class NullHandle(object):
    def close(self):
        pass


class CallsStasis(object):

    def __init__(self, ari_client, collectd, bus_publisher, services, xivo_uuid):
        self.ari = ari_client
        self.collectd = collectd
        self.bus_publisher = bus_publisher
        self.services = services
        self.xivo_uuid = xivo_uuid
        self.subscribe_all_channels_handle = NullHandle()

    def subscribe(self):
        self.ari.on_channel_event('StasisStart', self.bridge_connect_user)
        self.ari.on_channel_event('StasisStart', self.stat_new_call)
        self.ari.on_channel_event('StasisStart', self.stat_connect_call)
        self.subscribe_all_channels_handle = self.ari.on_channel_event('StasisStart', self.subscribe_to_all_channel_events)

    def subscribe_to_all_channel_events(self, event_objects, event):
        self.subscribe_all_channels_handle.close()
        self.ari.applications.subscribe(applicationName='callcontrol', eventSource='channel:')

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

    def stat_new_call(self, event_objects, event):
        if event['args'][0] != 'dialed_from':
            channel = event_objects['channel']
            channel.on_event('ChannelDestroyed', self.stat_end_call)
            channel.on_event('ChannelDestroyed', self.stat_call_duration)
            channel.on_event('ChannelDestroyed', self.stat_abandoned_call)
            bus_event = 'PUTVAL {xivo_uuid}/calls-callcontrol.sw1/counter-start interval=1 N:{increment}'
            bus_event = bus_event.format(increment=1, xivo_uuid=self.xivo_uuid)
            self.collectd.publish(CallStartCollectdEvent('callcontrol', 'sw1', event_objects['channel'].id))

    def stat_connect_call(self, event_objects, event):
        if event['args'][0] == 'dialed_from':
            self.collectd.publish(CallConnectCollectdEvent('callcontrol', 'sw1', event_objects['channel'].id))

    def stat_end_call(self, channel, event):
        self.collectd.publish(CallEndCollectdEvent('callcontrol', 'sw1', channel.id))

    def stat_call_duration(self, channel, event):
        start_time = channel.json['creationtime']
        start_datetime = datetime.datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S.%f-0500")

        end_time = event['timestamp']
        end_datetime = datetime.datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%S.%f-0500")

        duration = (end_datetime - start_datetime).seconds
        self.collectd.publish(CallDurationCollectdEvent('callcontrol', 'sw1', channel.id, duration))

    def stat_abandoned_call(self, channel, event):
        connected = channel.json['connected']
        if not connected.get('number'):
            self.collectd.publish(CallAbandonedCollectdEvent('callcontrol', 'sw1', channel.id))
