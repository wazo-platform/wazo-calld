# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

logger = logging.getLogger(__name__)


class SwitchboardsStasis(object):

    def __init__(self, ari, switchboard_service):
        self._ari = ari
        self._service = switchboard_service

    def subscribe(self):
        self._ari.on_channel_event('StasisStart', self.stasis_start)

    def stasis_start(self, event_objects, event):
        if 'args' not in event:
            return
        if len(event['args']) < 2:
            return
        if event['args'][0] != 'switchboard_queue':
            return

        switchboard_uuid = event['args'][1]
        channel = event_objects['channel']
        self._service.new_queued_call(switchboard_uuid, channel.id)
