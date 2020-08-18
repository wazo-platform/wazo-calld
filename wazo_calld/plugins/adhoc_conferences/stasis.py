# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import threading

from ari.exceptions import ARINotFound
from wazo_calld.plugin_helpers.ari_ import Bridge, Channel

import logging

logger = logging.getLogger(__name__)

ADHOC_CONFERENCE_STASIS_APP = 'adhoc_conference'


class AdhocConferencesStasis:

    def __init__(self, ari, notifier):
        self.ari = ari.client
        self._core_ari = ari
        self._notifier = notifier
        self.adhoc_conference_creation_lock = threading.Lock()

    def _subscribe(self):
        self.ari.on_channel_event('StasisStart', self.on_stasis_start)
        self.ari.on_channel_event('ChannelLeftBridge', self.on_channel_left_bridge)
        self.ari.on_bridge_event('BridgeDestroyed', self.on_bridge_destroyed)

    def initialize(self):
        self._subscribe()
        self._core_ari.register_application(ADHOC_CONFERENCE_STASIS_APP)

    def on_stasis_start(self, event_objects, event):
        if event['application'] != ADHOC_CONFERENCE_STASIS_APP:
            return

        logger.debug('on_stasis_start: %(id)s (%(name)s)', event['channel'])
        try:
            (adhoc_conference_id,) = event['args']
        except ValueError:
            logger.debug('ignoring StasisStart event: channel %s, app %s, args %s',
                         event['channel']['name'],
                         event['application'],
                         event['args'])
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
                self.ari.applications.subscribe(
                    applicationName=ADHOC_CONFERENCE_STASIS_APP,
                    eventSource=f'bridge:{bridge.id}',
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
            bridge_helper = Bridge(bridge.id, self.ari)
            bridge_helper.global_variables.set('WAZO_HOST_CHANNEL_ID', channel_id)
            host_user_uuid = Channel(channel_id, self.ari).user()
            bridge_helper.global_variables.set('WAZO_HOST_USER_UUID', host_user_uuid)

    def on_channel_left_bridge(self, channel, event):
        if event['application'] != ADHOC_CONFERENCE_STASIS_APP:
            return

        adhoc_conference_id = event['bridge']['id']
        channel_id = event['channel']['id']

        logger.debug('adhoc conference %s: channel %s left', adhoc_conference_id, channel_id)

        bridge_helper = Bridge(adhoc_conference_id, self.ari)
        try:
            adhoc_conference_host_channel_id = bridge_helper.global_variables.get(variable='WAZO_HOST_CHANNEL_ID')
        except KeyError:
            logger.error('adhoc conference %s: could not retrieve host channel id', adhoc_conference_id)
            return

        if adhoc_conference_host_channel_id == channel_id:
            logger.debug('adhoc conference %s: host %s left, hanging up all participants', adhoc_conference_id, channel_id)
            self._hangup_all_participants(adhoc_conference_id)
        elif bridge_helper.has_lone_channel():
            logger.debug('adhoc conference %s: only one participant %s left, hanging up', adhoc_conference_id, channel_id)
            bridge_helper.hangup_all()
        elif bridge_helper.is_empty():
            logger.debug('adhoc conference %s: bridge is empty, destroying', adhoc_conference_id)
            try:
                self.ari.bridges.destroy(bridgeId=adhoc_conference_id)
            except ARINotFound:
                pass

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

    def on_bridge_destroyed(self, bridge, event):
        if event['application'] != ADHOC_CONFERENCE_STASIS_APP:
            return

        logger.debug('adhoc conference %s: bridge was destroyed', bridge.id)

        try:
            host_user_uuid = Bridge(bridge.id, self.ari).global_variables.get('WAZO_HOST_USER_UUID')
        except KeyError:
            logger.error('adhoc conference %s: could not retrieve host user uuid', bridge.id)
            return

        self._notifier.deleted(bridge.id, host_user_uuid)

        host_user_uuid = Bridge(bridge.id, self.ari).global_variables.unset('WAZO_HOST_USER_UUID')
        host_user_uuid = Bridge(bridge.id, self.ari).global_variables.unset('WAZO_HOST_CHANNEL_ID')
