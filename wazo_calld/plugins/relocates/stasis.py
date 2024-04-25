# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from wazo_calld.ari_ import DEFAULT_APPLICATION_NAME

logger = logging.getLogger(__name__)


class RelocatesStasis:
    def __init__(self, ari, relocates):
        self.ari = ari.client
        self._core_ari = ari
        self.relocates = relocates

    def _subscribe(self):
        self.ari.on_channel_event('StasisStart', self.on_stasis_start)
        self.ari.on_channel_event('ChannelDestroyed', self.on_hangup)
        self.ari.on_channel_event('StasisEnd', self.on_hangup)

    def initialize(self):
        self._subscribe()
        self._core_ari.register_application(DEFAULT_APPLICATION_NAME)

    def on_stasis_start(self, event_objects, event):
        try:
            sub_app, *_ = event['args']
        except ValueError:
            return

        if sub_app != 'relocate':
            return

        try:
            sub_app, relocate_uuid, role = event['args']
        except ValueError:
            logger.debug(
                'ignoring StasisStart event: channel %s, app %s, args %s',
                event['channel']['name'],
                event['application'],
                event['args'],
            )
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
            logger.debug(
                'ignoring StasisEnd event: channel %s, app %s',
                event['channel']['name'],
                event['application'],
            )
            return
        with relocate.locked():
            role = relocate.role(channel.id)
            if role == 'recipient':
                relocate.recipient_hangup()
            elif role == 'relocated':
                relocate.relocated_hangup()
            elif role == 'initiator':
                relocate.initiator_hangup()
