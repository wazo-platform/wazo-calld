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

logger = logging.getLogger(__name__)


class CoreARI(object):

    def __init__(self, config):
        self.config = config
        self.client = ari.connect(**self.config['connection'])
        self.switchboard = Switchboard(self.client)

    def run(self):
        self.client.on_channel_event('StasisStart', on_start)
        try:
            self.client.run(self.config['apps'])
        finally:
            self.switchboard.destroy()


def on_start(channel, event):
    logger.info(channel)
    logger.info(event)


class Switchboard(object):

    def __init__(self, ari_client):
        self.ari = ari_client
        self.waiting_bridge_id = '123456'
        try:
            self.ari.bridges.create(type='holding', bridgeId=self.waiting_bridge_id, name='switchboard')
        except requests.RequestException as e:
            logger.debug(e.response.content)
            logger.exception(e)
        self.ari.on_channel_event('StasisStart', self.on_channel_event)

    def destroy(self):
        self.ari.bridges.destroy(bridgeId=self.waiting_bridge_id)

    def on_channel_event(self, channel, event):
        channel = channel['channel']
        channel.answer()
        try:
            self.ari.bridges.addChannel(bridgeId=self.waiting_bridge_id, channel=channel.id)
            self.ari.bridges.startMoh(bridgeId=self.waiting_bridge_id, mohClass='default')
        except requests.RequestException as e:
            logger.debug(e.response.content)
            logger.exception(e)
