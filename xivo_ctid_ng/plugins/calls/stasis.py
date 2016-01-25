# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import datetime
import logging

logger = logging.getLogger(__name__)


class CallsStasis(object):

    def __init__(self, ari_client, bus_collectd_publisher, bus_publisher, services, xivo_uuid):
        self.ari = ari_client
        self.bus_collectd_publisher = bus_collectd_publisher
        self.bus_publisher = bus_publisher
        self.services = services
        self.xivo_uuid = xivo_uuid
        self.subscribe_all_channels_handle = None

    def subscribe(self):
        self.ari.on_channel_event('StasisStart', self.bridge_connect_user)
        self.ari.on_channel_event('StasisStart', self.stat_new_call)
        self.ari.on_channel_event('StasisStart', self.stat_connect_call)
        self.subscribe_all_channels_handle = self.ari.on_channel_event('StasisStart', self.subscribe_to_all_channel_events)

    def subscribe_to_all_channel_events(self, event_objects, event):
        if self.subscribe_all_channels_handle:
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

    def stat_connect_call(self, event_objects, event):
        if event['args'][0] == 'dialed_from':
            bus_event = 'PUTVAL {xivo_uuid}/calls-callcontrol.sw1/counter-connect interval=1 N:{increment}'
            bus_event = bus_event.format(increment=1, xivo_uuid=self.xivo_uuid)
            self.bus_collectd_publisher.publish(bus_event)

    def stat_new_call(self, event_objects, event):
        logger.critical(event)
        if event['args'][0] != 'dialed_from':
            channel = event_objects['channel']
            logger.critical('StasisStart')
            channel.on_event('ChannelDestroyed', self.stat_end_call)
            channel.on_event('ChannelDestroyed', self.stat_call_duration)
            channel.on_event('ChannelDestroyed', self.stat_abandoned_call)
            bus_event = 'PUTVAL {xivo_uuid}/calls-callcontrol.sw1/counter-start interval=1 N:{increment}'
            bus_event = bus_event.format(increment=1, xivo_uuid=self.xivo_uuid)
            self.bus_collectd_publisher.publish(bus_event)

    def stat_end_call(self, channel, event):
        bus_event = 'PUTVAL {xivo_uuid}/calls-callcontrol.sw1/counter-end interval=1 N:{increment}'
        bus_event = bus_event.format(increment=1, xivo_uuid=self.xivo_uuid)
        self.bus_collectd_publisher.publish(bus_event)

    def stat_call_duration(self, channel, event):
        start_time = channel.json['creationtime']
        start_datetime = datetime.datetime.strptime(start_time, "%Y-%m-%dT%H:%M:%S.%f-0500")

        end_time = event['timestamp']
        end_datetime = datetime.datetime.strptime(end_time, "%Y-%m-%dT%H:%M:%S.%f-0500")

        duration = (end_datetime - start_datetime).seconds
        bus_event = 'PUTVAL {xivo_uuid}/calls-callcontrol.sw1/gauge-duration interval=1 N:{value}'
        bus_event = bus_event.format(value=duration, xivo_uuid=self.xivo_uuid)
        self.bus_collectd_publisher.publish(bus_event)

    def stat_abandoned_call(self, channel, event):
        connected = channel.json['connected']
        if not connected.get('number'):
            bus_event = 'PUTVAL {xivo_uuid}/calls-callcontrol.sw1/counter-abandoned interval=1 N:{increment}'
            bus_event = bus_event.format(increment=1, xivo_uuid=self.xivo_uuid)
            self.bus_collectd_publisher.publish(bus_event)
