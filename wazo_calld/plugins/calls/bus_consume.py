# Copyright 2016-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from ari.exceptions import ARINotFound
from xivo_bus.collectd.channels import ChannelCreatedCollectdEvent
from xivo_bus.collectd.channels import ChannelEndedCollectdEvent

from wazo_calld.plugin_helpers import ami
from wazo_calld.plugin_helpers.ari_ import Channel, set_channel_id_var_sync
from wazo_calld.plugin_helpers.exceptions import WazoAmidError
from .call import Call

logger = logging.getLogger(__name__)


class CallsBusEventHandler:

    def __init__(self, ami, ari, collectd, bus_publisher, services, xivo_uuid, dial_echo_manager, notifier):
        self.ami = ami
        self.ari = ari
        self.collectd = collectd
        self.bus_publisher = bus_publisher
        self.services = services
        self.xivo_uuid = xivo_uuid
        self.dial_echo_manager = dial_echo_manager
        self.notifier = notifier

    def subscribe(self, bus_consumer):
        bus_consumer.subscribe('Newchannel', self._add_sip_call_id)
        bus_consumer.subscribe('Newchannel', self._relay_channel_created)
        bus_consumer.subscribe('Newchannel', self._collectd_channel_created)
        bus_consumer.subscribe('Newstate', self._relay_channel_updated)
        bus_consumer.subscribe('Newstate', self._relay_channel_answered)
        bus_consumer.subscribe('NewConnectedLine', self._relay_channel_updated)
        bus_consumer.subscribe('Hold', self._channel_hold)
        bus_consumer.subscribe('Unhold', self._channel_unhold)
        bus_consumer.subscribe('Hangup', self._collectd_channel_ended)
        bus_consumer.subscribe('UserEvent', self._relay_user_missed_call)
        bus_consumer.subscribe('UserEvent', self._set_dial_echo_result)
        bus_consumer.subscribe('DTMFEnd', self._relay_dtmf)
        bus_consumer.subscribe('BridgeEnter', self._relay_channel_entered_bridge)
        bus_consumer.subscribe('BridgeLeave', self._relay_channel_left_bridge)
        bus_consumer.subscribe('MixMonitorStart', self._mix_monitor_start)
        bus_consumer.subscribe('MixMonitorStop', self._mix_monitor_stop)
        bus_consumer.subscribe(
            'users_services_dnd_updated', self._users_services_dnd_updated
        )

    def _add_sip_call_id(self, event):
        if not event['Channel'].startswith('PJSIP/'):
            return
        channel_id = event['Uniqueid']
        channel = Channel(channel_id, self.ari)
        sip_call_id = channel.sip_call_id_unsafe()
        if not sip_call_id:
            return

        try:
            self.ari.channels.setChannelVar(
                channelId=channel_id,
                variable='WAZO_SIP_CALL_ID',
                value=sip_call_id,
                bypassStasis=True,
            )
        except ARINotFound:
            logger.debug('channel %s not found', channel_id)

    def _relay_channel_created(self, event):
        channel_id = event['Uniqueid']
        if event['Channel'].startswith('Local/'):
            logger.debug('Ignoring local channel creation: %s', channel_id)
            return
        logger.debug('Relaying to bus: channel %s created', channel_id)
        try:
            channel = self.ari.channels.get(channelId=channel_id)
        except ARINotFound:
            logger.debug('channel %s not found', channel_id)
            return
        call = self.services.make_call_from_channel(self.ari, channel)
        self.notifier.call_created(call)

    def _collectd_channel_created(self, event):
        channel_id = event['Uniqueid']
        logger.debug('sending stat for new channel %s', channel_id)
        self.collectd.publish(ChannelCreatedCollectdEvent())

    def _relay_channel_updated(self, event):
        channel_id = event['Uniqueid']
        if event['Channel'].startswith('Local/'):
            logger.debug('Ignoring local channel update: %s', channel_id)
            return
        logger.debug('Relaying to bus: channel %s updated', channel_id)
        try:
            channel = self.ari.channels.get(channelId=channel_id)
        except ARINotFound:
            logger.debug('channel %s not found', channel_id)
            return
        call = self.services.make_call_from_channel(self.ari, channel)
        self.notifier.call_updated(call)

    def _relay_channel_answered(self, event):
        if event['ChannelStateDesc'] != 'Up':
            return
        channel_id = event['Uniqueid']
        if event['Channel'].startswith('Local/'):
            logger.debug('Ignoring local channel answer: %s', channel_id)
            return

        logger.debug('Relaying to bus: channel %s answered', channel_id)
        self.services.set_answered_time(channel_id)
        try:
            channel = self.ari.channels.get(channelId=channel_id)
        except ARINotFound:
            logger.debug('channel %s not found', channel_id)
            return
        call = self.services.make_call_from_channel(self.ari, channel)
        self.notifier.call_answered(call)

    def _collectd_channel_ended(self, event):
        channel_id = event['Uniqueid']
        logger.debug('sending stat for channel ended %s', channel_id)
        self.collectd.publish(ChannelEndedCollectdEvent())

    def _partial_call_from_channel_id(self, channel_id):
        channel = Channel(channel_id, self.ari)
        call = Call(channel.id)
        call.user_uuid = channel.user()
        call.tenant_uuid = channel.tenant_uuid()
        return call

    def _channel_hold(self, event):
        channel_id = event['Uniqueid']
        logger.debug('marking channel %s on hold', channel_id)
        ami.set_variable_ami(self.ami, channel_id, 'XIVO_ON_HOLD', '1')

        call = self._partial_call_from_channel_id(channel_id)
        self.notifier.call_hold(call)

    def _channel_unhold(self, event):
        channel_id = event['Uniqueid']
        logger.debug('marking channel %s not on hold', channel_id)
        ami.unset_variable_ami(self.ami, channel_id, 'XIVO_ON_HOLD')

        call = self._partial_call_from_channel_id(channel_id)
        self.notifier.call_resume(call)

    def _relay_user_missed_call(self, event):
        if event['UserEvent'] != 'user_missed_call':
            return

        logger.debug('Got UserEvent user_missed_call: %s', event)

        user_uuid = event['destination_user_uuid']
        tenant_uuid = event['ChanVariable']['WAZO_TENANT_UUID']
        reason = event['reason']

        # hangup_cause 3: no route to destination
        if reason == 'channel-unavailable' and event['hangup_cause'] == '3':
            reason = 'phone-unreachable'

        payload = {
            'user_uuid': user_uuid,
            'tenant_uuid': tenant_uuid,
            'caller_user_uuid': event['caller_user_uuid'] or None,
            'caller_id_name': event['caller_id_name'],
            'caller_id_number': event['caller_id_number'],
            'dialed_extension': event['entry_exten'],
            'conversation_id': event['conversation_id'],
            'reason': reason,
        }
        self.notifier.user_missed_call(payload)

    def _set_dial_echo_result(self, event):
        if event['UserEvent'] != 'dial_echo':
            return

        logger.debug('Got UserEvent dial_echo: %s', event)
        self.dial_echo_manager.set_dial_echo_result(
            event['wazo_dial_echo_request_id'],
            {'channel_id': event['channel_id']}
        )

    def _relay_dtmf(self, event):
        channel_id = event['Uniqueid']
        digit = event['Digit']
        logger.debug('Relaying to bus: channel %s DTMF digit %s', channel_id, digit)
        call = self._partial_call_from_channel_id(channel_id)
        self.notifier.call_dtmf(call, digit)

    def _relay_channel_entered_bridge(self, event):
        channel_id = event['Uniqueid']
        bridge_id = event['BridgeUniqueid']
        logger.debug('Relaying to bus: channel %s entered bridge %s', channel_id, bridge_id)
        if int(event['BridgeNumChannels']) == 1:
            logger.debug('ignoring channel %s entered bridge %s: channel is alone', channel_id, bridge_id)
            return

        try:
            participant_channel_ids = self.ari.bridges.get(bridgeId=bridge_id).json['channels']
        except ARINotFound:
            logger.debug('bridge %s not found', bridge_id)
            return

        set_channel_id_var_sync(
            self.ari,
            channel_id,
            '__WAZO_CONVERSATION_DIRECTION',
            self.services.conversation_direction_from_channels(participant_channel_ids),
            bypass_stasis=True,
        )

        for participant_channel_id in participant_channel_ids:
            try:
                channel = self.ari.channels.get(channelId=participant_channel_id)
            except ARINotFound:
                logger.debug('channel %s not found', participant_channel_id)
                return

            call = self.services.make_call_from_channel(self.ari, channel)
            self.notifier.call_updated(call)

    def _relay_channel_left_bridge(self, event):
        channel_id = event['Uniqueid']
        bridge_id = event['BridgeUniqueid']
        if int(event['BridgeNumChannels']) == 0:
            logger.debug('ignoring channel %s left bridge %s: bridge is empty', channel_id, bridge_id)
            return

        logger.debug('Relaying to bus: channel %s left bridge %s', channel_id, bridge_id)

        try:
            participant_channel_ids = self.ari.bridges.get(bridgeId=bridge_id).json['channels']
        except ARINotFound:
            logger.debug('bridge %s not found', bridge_id)
            return

        set_channel_id_var_sync(
            self.ari,
            channel_id,
            '__WAZO_CONVERSATION_DIRECTION',
            self.services.conversation_direction_from_channels(participant_channel_ids),
            bypass_stasis=True,
        )

        for participant_channel_id in participant_channel_ids:
            try:
                channel = self.ari.channels.get(channelId=participant_channel_id)
            except ARINotFound:
                logger.debug('channel %s not found', participant_channel_id)
                return

            call = self.services.make_call_from_channel(self.ari, channel)
            self.notifier.call_updated(call)

    def _mix_monitor_start(self, event):
        channel_id = event['Uniqueid']
        try:
            set_channel_id_var_sync(
                self.ari,
                channel_id,
                'WAZO_CALL_RECORD_ACTIVE',
                '1',
                bypass_stasis=True,
            )
        except ARINotFound:
            logger.debug('channel %s not found', channel_id)
            return
        self._relay_channel_updated(event)

    def _mix_monitor_stop(self, event):
        channel_id = event['Uniqueid']
        try:
            set_channel_id_var_sync(
                self.ari,
                channel_id,
                'WAZO_CALL_RECORD_ACTIVE',
                '0',
                bypass_stasis=True,
            )
        except ARINotFound:
            logger.debug('channel %s not found', channel_id)
            return
        self._relay_channel_updated(event)

    def _users_services_dnd_updated(self, event):
        user_uuid = event['user_uuid']
        enabled = event['enabled']
        interface = f'Local/{user_uuid}@usersharedlines'
        try:
            if enabled:
                ami.pause_queue_member(self.ami, interface)
            else:
                ami.unpause_queue_member(self.ami, interface)
        except WazoAmidError as e:
            if e.details['original_error'] == 'Interface not found':
                logger.debug('%s is not a member of any group. Not changing pause status', interface)
                return
            raise
