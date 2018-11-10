# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

logger = logging.getLogger(__name__)


class RelocatesStasis(object):

    def __init__(self, ari_client, relocates):
        self.ari = ari_client
        self.relocates = relocates

    def subscribe(self):
        self.ari.on_channel_event('StasisStart', self.on_stasis_start)
        self.ari.on_channel_event('ChannelDestroyed', self.on_hangup)
        self.ari.on_channel_event('StasisEnd', self.on_hangup)

    def on_stasis_start(self, event_objects, event):
        logger.debug('on_stasis_start: %(id)s (%(name)s)', event['channel'])
        try:
            sub_app, relocate_uuid, role = event['args']
        except ValueError:
            logger.debug('ignoring StasisStart event: channel %s, app %s, args %s',
                         event['channel']['name'],
                         event['application'],
                         event['args'])
            return

        if sub_app != 'relocate':
            return

        relocate = self.relocates.get(relocate_uuid)
        with relocate.locked():
            if role == 'recipient':
                relocate.recipient_answered()
            elif role == 'relocated':
                relocate.relocated_answered()

    def on_hangup(self, channel, event):
        logger.debug('on_hangup: %(id)s (%(name)s)', event['channel'])
        try:
            relocate = self.relocates.get_by_channel(channel.id)
        except KeyError:
            logger.debug('ignoring StasisEnd event: channel %s, app %s', event['channel']['name'], event['application'])
            return
        with relocate.locked():
            role = relocate.role(channel.id)
            if role == 'recipient':
                relocate.recipient_hangup()
            elif role == 'relocated':
                relocate.relocated_hangup()
            elif role == 'initiator':
                relocate.initiator_hangup()
