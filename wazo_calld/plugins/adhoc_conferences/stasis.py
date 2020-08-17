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
        self.ari.on_channel_event('ChannelLeftBridge', self.on_channel_left_bridge)

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

        channel = event_objects['channel']
        try:
            is_adhoc_conference_host = channel.getChannelVar(variable='WAZO_IS_ADHOC_CONFERENCE_HOST')['value'] == 'true'
        except ARINotFound:
            logger.error('adhoc conference %s: channel %s hungup too early or variable not found', adhoc_conference_id, channel_id)
            return

        if is_adhoc_conference_host:
            try:
                bridge.setBridgeVar(variable='WAZO_ADHOC_CONFERENCE_HOST', value=channel_id)
            except ARINotFound:
                logger.error('adhoc conference %s: bridge was destroyed too early when join')
                return

    def on_channel_left_bridge(self, channel, event):
        adhoc_conference_id = event['bridge']['id']
        channel_id = event['channel']['id']

        if not self._channel_left_adhoc_conference(channel_id, adhoc_conference_id):
            logger.debug('adhoc conference: ignoring channel %s left bridge', channel_id)
            return

        logger.debug('adhoc conference %s: channel %s left', adhoc_conference_id, channel_id)

        try:
            adhoc_conference_host_channel_id = self.ari.bridges.getBridgeVar(bridgeId=adhoc_conference_id, variable='WAZO_ADHOC_CONFERENCE_HOST').get('WAZO_ADHOC_CONFERENCE_HOST')
        except ARINotFound:
            logger.error('adhoc conference %s: bridge was destroyed too early when leaving')
            return

        if adhoc_conference_host_channel_id == channel_id:
            logger.debug('adhoc conference %s: host %s left, hanging up all participants', adhoc_conference_id, channel_id)
            self._hangup_all_participants(adhoc_conference_id)

    def _hangup_all_participants(self, adhoc_conference_id):
        try:
            channel_ids = self.ari.bridges.get(bridgeId=adhoc_conference_id).json['channels']
        except ARINotFound:
            logger.error('adhoc conference %s: bridge was destroyed too early when destroying', adhoc_conference_id)
            return

        logger.debug('adhoc conference %s: found %s participants', adhoc_conference_id, len(channel_ids))
        for channel_id in channel_ids:
            logger.debug('adhoc conference %s: hanging up participant %s', adhoc_conference_id, channel_id)
            try:
                self.ari.channels.hangup(channelId=channel_id)
            except ARINotFound:
                pass

        logger.debug('adhoc conference %s: destroying bridge', adhoc_conference_id)
        try:
            self.ari.bridges.destroy(bridgeId=adhoc_conference_id)
        except ARINotFound:
            pass

    def _channel_left_adhoc_conference(self, channel_id, bridge_id):
        try:
            self.ari.bridges.getBridgeVar(bridgeId=bridge_id, variable='WAZO_ADHOC_CONFERENCE_HOST').get('WAZO_ADHOC_CONFERENCE_HOST')
        except ARINotFound:
            return False
        return True
