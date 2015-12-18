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

import ari
import logging
import requests
import socket

from .exceptions import ARIUnreachable

logger = logging.getLogger(__name__)


class CoreCallControl(object):

    def __init__(self, config):
        try:
            self.ari = ari.connect(**config['connection'])
        except requests.ConnectionError:
            logger.critical('ARI config: %s', config['connection'])
            raise ARIUnreachable()
        self.callcontrol = CallControl(self.ari)

    def run(self):
        try:
            self.ari.run(apps=['callcontrol'])
        except socket.error as e:
            logger.error('Error while listening for ARI events: %s', e)  # bug in ari-py when calling client.close()

    def stop(self):
        try:
            self.ari.close()
        except RuntimeError:
            pass  # bug in ari-py when calling client.close()


class CallControl(object):

    def __init__(self, ari_client):
        self.ari = ari_client
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
