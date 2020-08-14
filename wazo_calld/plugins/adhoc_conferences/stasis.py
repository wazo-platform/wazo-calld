# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import threading

from ari.exceptions import ARINotFound
from wazo_calld.ari_ import DEFAULT_APPLICATION_NAME

import logging

logger = logging.getLogger(__name__)


class AdhocConferencesStasis:

    def __init__(self, ari):
        self.ari = ari.client
        self._core_ari = ari
        self.adhoc_conference_creation_lock = threading.Lock()

    def _subscribe(self):
        self.ari.on_channel_event('StasisStart', self.on_stasis_start)

    def initialize(self):
        self._subscribe()
        self._core_ari.register_application(DEFAULT_APPLICATION_NAME)

    def on_stasis_start(self, event_objects, event):
        logger.debug('on_stasis_start: %(id)s (%(name)s)', event['channel'])
        try:
            sub_app, adhoc_conference_id = event['args']
        except ValueError:
            logger.debug('ignoring StasisStart event: channel %s, app %s, args %s',
                         event['channel']['name'],
                         event['application'],
                         event['args'])
            return

        if sub_app != 'adhoc_conference':
            return

        with self.adhoc_conference_creation_lock:
            try:
                bridge = self.ari.bridges.get(bridgeId=adhoc_conference_id)
            except ARINotFound:
                logger.debug('adhoc conference %s: creating bridge', adhoc_conference_id)
                bridge = self.ari.bridges.createWithId(
                    type='mixing',
                    bridgeId=adhoc_conference_id,
                )
        channel_id = event['channel']['id']
        logger.debug('adhoc conference %s: bridging participant %s', adhoc_conference_id, channel_id)
        bridge.addChannel(channel=channel_id)
