# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from .exceptions import NoSuchSwitchboard

logger = logging.getLogger(__name__)


class SwitchboardsStasis(object):

    def __init__(self, ari, switchboard_notifier, switchboard_service):
        self._ari = ari
        self._notifier = switchboard_notifier
        self._service = switchboard_service

    def subscribe(self):
        self._ari.on_channel_event('StasisStart', self.stasis_start)
        self._ari.on_channel_event('ChannelLeftBridge', self.unqueue)

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

    def unqueue(self, channel, event):
        switchboard_uuid = channel.json['channelvars']['WAZO_SWITCHBOARD_QUEUE']

        try:
            queued_calls = self._service.queued_calls(switchboard_uuid)
        except NoSuchSwitchboard:
            return

        self._notifier.queued_calls(switchboard_uuid, queued_calls)
