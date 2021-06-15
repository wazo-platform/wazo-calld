# Copyright 2016-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from ari.exceptions import ARINotFound
from xivo_bus.collectd.channels import ChannelCreatedCollectdEvent
from xivo_bus.collectd.channels import ChannelEndedCollectdEvent
from xivo_bus.resources.calls.dtmf import CallDTMFEvent
from xivo_bus.resources.calls.hold import CallOnHoldEvent
from xivo_bus.resources.calls.hold import CallResumeEvent
from xivo_bus.resources.calls.missed import UserMissedCall
from xivo_bus.resources.common.event import ArbitraryEvent

from wazo_calld.plugin_helpers import ami
from wazo_calld.plugin_helpers.ari_ import Channel, set_channel_id_var_sync

from .schemas import call_schema

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
        bus_consumer.on_ami_event('Newchannel', self._add_sip_call_id)
        bus_consumer.on_ami_event('Newchannel', self._relay_channel_created)
        bus_consumer.on_ami_event('Newchannel', self._collectd_channel_created)
        bus_consumer.on_ami_event('Newstate', self._relay_channel_updated)
        bus_consumer.on_ami_event('Newstate', self._relay_channel_answered)
        bus_consumer.on_ami_event('NewConnectedLine', self._relay_channel_updated)
        bus_consumer.on_ami_event('Hold', self._channel_hold)
        bus_consumer.on_ami_event('Unhold', self._channel_unhold)
        bus_consumer.on_ami_event('Hangup', self._collectd_channel_ended)
        bus_consumer.on_ami_event('UserEvent', self._relay_user_missed_call)
        bus_consumer.on_ami_event('UserEvent', self._set_dial_echo_result)
        bus_consumer.on_ami_event('DTMFEnd', self._relay_dtmf)
        bus_consumer.on_ami_event('BridgeEnter', self._relay_channel_entered_bridge)
        bus_consumer.on_ami_event('BridgeLeave', self._relay_channel_left_bridge)
        bus_consumer.on_ami_event('MixMonitorStart', self._mix_monitor_start)
        bus_consumer.on_ami_event('MixMonitorStop', self._mix_monitor_stop)

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
        bus_event = ArbitraryEvent(
            name='call_created',
            body=call_schema.dump(call),
            required_acl='events.calls.{}'.format(call.user_uuid)
        )
        bus_event.routing_key = 'calls.call.created'
        self.bus_publisher.publish(bus_event, headers={'user_uuid:{uuid}'.format(uuid=call.user_uuid): True})

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

    def _channel_hold(self, event):
        channel_id = event['Uniqueid']
        logger.debug('marking channel %s on hold', channel_id)
        ami.set_variable_ami(self.ami, channel_id, 'XIVO_ON_HOLD', '1')

        user_uuid = Channel(channel_id, self.ari).user()
        bus_msg = CallOnHoldEvent(channel_id, user_uuid)
        self.bus_publisher.publish(bus_msg, headers={'user_uuid:{uuid}'.format(uuid=user_uuid): True})

    def _channel_unhold(self, event):
        channel_id = event['Uniqueid']
        logger.debug('marking channel %s not on hold', channel_id)
        ami.unset_variable_ami(self.ami, channel_id, 'XIVO_ON_HOLD')

        user_uuid = Channel(channel_id, self.ari).user()
        bus_msg = CallResumeEvent(channel_id, user_uuid)
        self.bus_publisher.publish(bus_msg, headers={'user_uuid:{uuid}'.format(uuid=user_uuid): True})

    def _relay_user_missed_call(self, event):
        if event['UserEvent'] != 'user_missed_call':
            return

        logger.debug('Got UserEvent user_missed_call: %s', event)

        user_uuid = event['destination_user_uuid']
        reason = event['reason']

        # hangup_cause 3: no route to destination
        if reason == 'channel-unavailable' and event['hangup_cause'] == '3':
            reason = 'phone-unreachable'

        bus_msg = UserMissedCall({
            'user_uuid': user_uuid,
            'caller_user_uuid': event['caller_user_uuid'] or None,
            'caller_id_name': event['caller_id_name'],
            'caller_id_number': event['caller_id_number'],
            'dialed_extension': event['entry_exten'],
            'conversation_id': event['conversation_id'],
            'reason': reason,
        })
        self.bus_publisher.publish(bus_msg, headers={f'user_uuid:{user_uuid}': True})

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
        user_uuid = Channel(channel_id, self.ari).user()
        bus_msg = CallDTMFEvent(channel_id, digit, user_uuid)
        self.bus_publisher.publish(bus_msg, headers={'user_uuid:{uuid}'.format(uuid=user_uuid): True})

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
