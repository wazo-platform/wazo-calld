# Copyright 2019-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

logger = logging.getLogger(__name__)


class DialMobileStasis:
    _app_name = 'dial_mobile'

    def __init__(self, ari, service):
        self._core_ari = ari
        self._ari = ari.client
        self._service = service

    def stasis_start(self, event_object, event):
        if event['application'] != self._app_name:
            return

        args = event['args']
        if len(args) < 2:
            logger.info('%s called without enough arguments %s', self._app_name, args)
            return

        action = args[0]
        channel_id = event['channel']['id']
        logger.debug('AFDEBUG: Stasis event: %s', event)
        logger.debug('AFDEBUG: action: %s channel_id: %s', action, channel_id)
        origin_channel_id = event['channel']['channelvars']['CHANNEL(linkedid)']

        if action == 'dial':
            aor = args[1]
            self._service.dial_all_contacts(channel_id, origin_channel_id, aor)
        elif action == 'join':
            future_bridge_uuid = args[1]
            self._service.join_bridge(channel_id, future_bridge_uuid)

    def on_channel_left_bridge(self, channel, event):
        if event['application'] != self._app_name:
            return

        bridge_id = event['bridge']['id']

        self._service.clean_bridge(bridge_id)

    def _add_ari_application(self):
        self._core_ari.register_application(self._app_name)

    def channel_destroyed(self, channel, event):
        self._service.notify_channel_gone(event['channel']['id'])

    def _subscribe(self):
        self._ari.on_channel_event('StasisStart', self.stasis_start)
        self._ari.on_channel_event('ChannelLeftBridge', self.on_channel_left_bridge)
        self._ari.on_channel_event('ChannelDestroyed', self.channel_destroyed)

    def initialize(self):
        self._subscribe()
        self._add_ari_application()
