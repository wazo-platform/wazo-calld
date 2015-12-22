# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+


class CallsStasis(object):

    def __init__(self, ari_client):
        self.ari = ari_client

    def subscribe(self):
        self.ari.on_channel_event('StasisStart', self.on_channel_event_start)

    def on_channel_event_start(self, event_objects, event):
        if not event.get('args'):
            return

        if event['args'][0] == 'dialed_from':
            originator_channel_id = event['args'][1]
            this_channel_id = event_objects['channel'].id
            bridge = self.ari.bridges.create(type='mixing')
            bridge.addChannel(channel=originator_channel_id)
            bridge.addChannel(channel=this_channel_id)
