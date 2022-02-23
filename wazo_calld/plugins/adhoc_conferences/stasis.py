# Copyright 2020-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import threading

from ari.exceptions import ARINotFound
from wazo_calld.plugin_helpers.ari_ import Bridge, BridgeSnapshot, Channel
from wazo_calld.plugins.calls.services import CallsService

import logging

logger = logging.getLogger(__name__)

ADHOC_CONFERENCE_STASIS_APP = 'adhoc_conference'


class AdhocConferencesStasis:

    def __init__(self, ari, notifier):
        self._ari = ari.client
        self._core_ari = ari
        self._notifier = notifier
        self._adhoc_conference_creation_lock = threading.Lock()

    def _subscribe(self):
        self._ari.on_channel_event('StasisStart', self.on_stasis_start)
        self._ari.on_channel_event('ChannelEnteredBridge', self.on_channel_entered_bridge)
        self._ari.on_channel_event('ChannelLeftBridge', self.on_channel_left_bridge)
        self._ari.on_bridge_event('BridgeDestroyed', self.on_bridge_destroyed)

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

        with self._adhoc_conference_creation_lock:
            try:
                bridge = self._ari.bridges.get(bridgeId=adhoc_conference_id)
            except ARINotFound:
                logger.debug('adhoc conference %s: creating bridge', adhoc_conference_id)
                bridge = self._ari.bridges.createWithId(
                    type='mixing',
                    bridgeId=adhoc_conference_id,
                )
                self._ari.applications.subscribe(
                    applicationName=ADHOC_CONFERENCE_STASIS_APP,
                    eventSource=f'bridge:{bridge.id}',
                )

        channel_id = event['channel']['id']
        logger.debug('adhoc conference %s: bridging participant %s', adhoc_conference_id, channel_id)
        bridge.addChannel(channel=channel_id, inhibitConnectedLineUpdates=True)

    def on_channel_entered_bridge(self, channel, event):
        if event['application'] != ADHOC_CONFERENCE_STASIS_APP:
            return

        adhoc_conference_id = event['bridge']['id']
        channel_id = event['channel']['id']

        logger.debug('adhoc conference %s: channel %s entered', adhoc_conference_id, channel_id)

        try:
            is_adhoc_conference_host = channel.getChannelVar(variable='WAZO_IS_ADHOC_CONFERENCE_HOST')['value'] == 'true'
        except ARINotFound:
            logger.error('adhoc conference %s: channel %s hungup too early or variable not found', adhoc_conference_id, channel_id)
            return

        bridge_helper = BridgeSnapshot(event['bridge'], self._ari)

        if is_adhoc_conference_host:
            host_channel = Channel(channel_id, self._ari)
            host_user_uuid = host_channel.user()
            host_tenant_uuid = host_channel.tenant_uuid()
            bridge_helper.global_variables.set('WAZO_HOST_CHANNEL_ID', channel_id)
            bridge_helper.global_variables.set('WAZO_HOST_USER_UUID', host_user_uuid)
            bridge_helper.global_variables.set('WAZO_HOST_TENANT_UUID', host_tenant_uuid)

            self._notify_host_of_channels_already_present(adhoc_conference_id, event['bridge']['channels'], host_user_uuid)

            logger.debug('adhoc conference %s: setting host connectedline', adhoc_conference_id)
            self._set_host_connectedline(channel_id, adhoc_conference_id)

        participant_call = CallsService.make_call_from_channel(self._ari, channel)
        other_participant_uuids = bridge_helper.valid_user_uuids()
        self._notifier.participant_joined(adhoc_conference_id, other_participant_uuids, participant_call)

    def _notify_host_of_channels_already_present(self, adhoc_conference_id, channel_ids, host_user_uuid):
        for channel_id in channel_ids:
            try:
                other_participant_channel = self._ari.channels.get(channelId=channel_id)
            except ARINotFound:
                logger.error('adhoc conference %s: participant %s hanged up before host arrived', adhoc_conference_id, channel_id)
                continue
            other_participant_call = CallsService.make_call_from_channel(self._ari, other_participant_channel)
            self._notifier.participant_joined(adhoc_conference_id, [host_user_uuid], other_participant_call)

    def _set_host_connectedline(self, channel_id, adhoc_conference_id):
        try:
            host_caller_id_number = self._ari.channels.getChannelVar(channelId=channel_id, variable='CALLERID(number)')['value']
            self._ari.channels.setChannelVar(channelId=channel_id, variable='CONNECTEDLINE(all)', value=f'"Conference" <{host_caller_id_number}>')
        except ARINotFound:
            logger.error('adhoc conference %s: channel %s hungup too early or variable not found when setting connected line', adhoc_conference_id, channel_id)
            return

    def on_channel_left_bridge(self, channel, event):
        if event['application'] != ADHOC_CONFERENCE_STASIS_APP:
            return

        adhoc_conference_id = event['bridge']['id']
        channel_id = event['channel']['id']

        logger.debug('adhoc conference %s: channel %s left', adhoc_conference_id, channel_id)

        bridge_helper = Bridge(adhoc_conference_id, self._ari)
        try:
            host_user_uuid = bridge_helper.global_variables.get('WAZO_HOST_USER_UUID')
        except KeyError:
            logger.error('adhoc conference %s: could not retrieve host user uuid when leaving', adhoc_conference_id)
            return

        participant_call = CallsService.make_call_from_dead_channel(channel)
        other_participant_uuids = bridge_helper.valid_user_uuids() | {host_user_uuid}
        self._notifier.participant_left(adhoc_conference_id, other_participant_uuids, participant_call)

        if bridge_helper.has_lone_channel():
            logger.debug('adhoc conference %s: only one participant %s left, hanging up', adhoc_conference_id, channel_id)
            bridge_helper.hangup_all()
        elif bridge_helper.is_empty():
            logger.debug('adhoc conference %s: bridge is empty, destroying', adhoc_conference_id)
            try:
                self._ari.bridges.destroy(bridgeId=adhoc_conference_id)
            except ARINotFound:
                pass
        else:
            try:
                adhoc_conference_host_channel_id = bridge_helper.global_variables.get(variable='WAZO_HOST_CHANNEL_ID')
            except KeyError:
                logger.error('adhoc conference %s: could not retrieve host channel id', adhoc_conference_id)
                return
            if adhoc_conference_host_channel_id == channel_id:
                logger.debug('adhoc conference %s: host %s left, hanging up all participants', adhoc_conference_id, channel_id)
                self._hangup_all_participants(adhoc_conference_id)

    def _hangup_all_participants(self, adhoc_conference_id):
        try:
            channel_ids = self._ari.bridges.get(bridgeId=adhoc_conference_id).json['channels']
        except ARINotFound:
            logger.error('adhoc conference %s: bridge was destroyed too early when destroying', adhoc_conference_id)
            return

        logger.debug('adhoc conference %s: found %s participants', adhoc_conference_id, len(channel_ids))
        for channel_id in channel_ids:
            logger.debug('adhoc conference %s: hanging up participant %s', adhoc_conference_id, channel_id)
            try:
                self._ari.channels.hangup(channelId=channel_id)
            except ARINotFound:
                pass

    def on_bridge_destroyed(self, bridge, event):
        if event['application'] != ADHOC_CONFERENCE_STASIS_APP:
            return

        logger.debug('adhoc conference %s: bridge was destroyed', bridge.id)
        bridge_helper = Bridge(bridge.id, self._ari)

        try:
            host_user_uuid = bridge_helper.global_variables.get('WAZO_HOST_USER_UUID')
        except KeyError:
            logger.error('adhoc conference %s: could not retrieve host user uuid when destroying', bridge.id)
            return

        try:
            host_tenant_uuid = bridge_helper.global_variables.get('WAZO_HOST_TENANT_UUID')
        except KeyError:
            logger.error('adhoc conference %s: could not retrieve host tenant uuid when destroying', bridge.id)
            return

        self._notifier.deleted(bridge.id, host_tenant_uuid, host_user_uuid)
        bridge_helper.global_variables.unset('WAZO_HOST_CHANNEL_ID')
        bridge_helper.global_variables.unset('WAZO_HOST_USER_UUID')
        bridge_helper.global_variables.unset('WAZO_HOST_TENANT_UUID')
