# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
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

        action = event['args'][0]
        channel_id = event['channel']['id']
        logger.debug('action: %s channel_id: %s', action, channel_id)

        if action == 'dial':
            aor = event['args'][1]
            self._service.dial_all_contacts(channel_id, aor)
        elif action == 'join':
            future_bridge_uuid = event['args'][1]
            self._service.join_bridge(channel_id, future_bridge_uuid)

    def add_ari_application(self):
        self._core_ari.register_application(self._app_name)
        self._core_ari.reload()

    def subscribe(self):
        self._ari.on_channel_event('StasisStart', self.stasis_start)
