# Copyright 2019-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

logger = logging.getLogger(__name__)

ARG_LEN_BY_COMMAND = {
    'dial': 2,
    'join': 2,
    'pickup': 3,
}


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
        channel_id = event['channel']['id']

        if not args or len(args) < ARG_LEN_BY_COMMAND[args[0]]:
            logger.info('%s called without enough arguments %s', self._app_name, args)
            return

        action = args[0]
        origin_channel_id = event['channel']['channelvars']['CHANNEL(linkedid)']

        if action == 'dial':
            aor = args[1]
            self._service.dial_all_contacts(channel_id, origin_channel_id, aor)
        elif action == 'join':
            future_bridge_uuid = args[1]
            self._service.join_bridge(channel_id, future_bridge_uuid)
        elif action == 'pickup':
            exten, context = args[1], args[2]
            future_bridge_uuid = self._service.find_bridge_by_exten_context(exten, context)
            if future_bridge_uuid:
                self._service.join_bridge(channel_id, future_bridge_uuid)
            else:
                logger.debug('no matching mobile pickup found')
                self._ari.channels.continueInDialplan(channelId=channel_id)

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
