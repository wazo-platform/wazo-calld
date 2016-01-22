# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

logger = logging.getLogger(__name__)


class CallsStasis(object):

    def __init__(self, ari_client, bus_publisher, services):
        self.ari = ari_client
        self.bus_publisher = bus_publisher
        self.services = services

    def subscribe(self):
        self.ari.on_channel_event('StasisStart', self.bridge_connect_user)

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
