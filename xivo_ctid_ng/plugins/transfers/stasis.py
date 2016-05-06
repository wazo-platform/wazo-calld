# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo.pubsub import Pubsub

from ari.exceptions import ARINotFound
from ari.exceptions import ARINotInStasis

from . import ari_helpers
from .event import TransferRecipientAnsweredEvent
from .event import CreateTransferEvent
from .exceptions import InvalidEvent
from .exceptions import TransferException
from .exceptions import XiVOAmidUnreachable
from .transfer import TransferRole

logger = logging.getLogger(__name__)


class TransfersStasis(object):

    def __init__(self, amid_client, ari_client, services, state_factory, state_persistor, xivo_uuid):
        self.ari = ari_client
        self.amid = amid_client
        self.services = services
        self.xivo_uuid = xivo_uuid
        self.stasis_start_pubsub = Pubsub()
        self.stasis_start_pubsub.set_exception_handler(self.invalid_event)
        self.hangup_pubsub = Pubsub()
        self.hangup_pubsub.set_exception_handler(self.invalid_event)
        self.state_factory = state_factory
        self.state_persistor = state_persistor

    def subscribe(self):
        self.ari.on_channel_event('ChannelEnteredBridge', self.release_hangup_lock)
        self.ari.on_channel_event('ChannelDestroyed', self.bypass_hangup_lock_from_source)
        self.ari.on_bridge_event('BridgeDestroyed', self.bypass_hangup_lock_from_target)
        self.ari.on_bridge_event('BridgeDestroyed', self.clean_bridge_variables)

        self.ari.on_channel_event('ChannelLeftBridge', self.clean_bridge)

        self.ari.on_channel_event('StasisStart', self.stasis_start)
        self.stasis_start_pubsub.subscribe('transfer_recipient_called', self.transfer_recipient_answered)
        self.stasis_start_pubsub.subscribe('create_transfer', self.create_transfer)

        self.ari.on_channel_event('ChannelDestroyed', self.hangup)
        self.ari.on_channel_event('StasisEnd', self.hangup)
        self.hangup_pubsub.subscribe(TransferRole.recipient, self.recipient_hangup)
        self.hangup_pubsub.subscribe(TransferRole.initiator, self.initiator_hangup)
        self.hangup_pubsub.subscribe(TransferRole.transferred, self.transferred_hangup)

    def invalid_event(self, _, __, exception):
        if isinstance(exception, InvalidEvent):
            event = exception.event
            logger.error('invalid stasis event received: %s', event)
        elif (isinstance(exception, XiVOAmidUnreachable) or
              isinstance(exception, TransferException)):
            self.handle_error(exception)
        else:
            raise

    def handle_error(self, exception):
        logger.error('%s: %s', exception.message, exception.details)

    def stasis_start(self, event_objects, event):
        channel = event_objects['channel']
        try:
            app_action = event['args'][1]
        except IndexError:
            logger.debug('ignoring StasisStart event: channel %s, app %s, args %s',
                         event['channel']['name'],
                         event['application'],
                         event['args'])
            return
        self.stasis_start_pubsub.publish(app_action, (channel, event))

    def hangup(self, channel, event):
        try:
            transfer = self.state_persistor.get_by_channel(channel.id)
        except KeyError:
            logger.debug('ignoring StasisEnd event: channel %s, app %s', event['channel']['name'], event['application'])
            return
        transfer_role = transfer.role(channel.id)
        self.hangup_pubsub.publish(transfer_role, transfer)

    def transfer_recipient_answered(self, (channel, event)):
        event = TransferRecipientAnsweredEvent(event)

        try:
            transfer_bridge = self.ari.bridges.get(bridgeId=event.transfer_bridge)
            transfer_bridge.addChannel(channel=channel.id)
        except ARINotFound:
            logger.error('recipient answered, but transfer was hung up')
            return

        try:
            transfer = self.state_persistor.get(event.transfer_bridge)
        except KeyError:
            logger.debug('recipient answered, but transfer was abandoned')

            for channel_id in transfer_bridge.json['channels']:
                try:
                    ari_helpers.unring_initiator_call(self.ari, channel_id)
                except ARINotFound:
                    pass
        else:
            logger.debug('recipient answered, transfer continues normally')
            transfer_state = self.state_factory.make(transfer)
            transfer_state.recipient_answer()

    def create_transfer(self, (channel, event)):
        event = CreateTransferEvent(event)
        try:
            bridge = self.ari.bridges.get(bridgeId=event.transfer_id)
        except ARINotFound:
            bridge = self.ari.bridges.createWithId(type='mixing', name='transfer', bridgeId=event.transfer_id)

        bridge.addChannel(channel=channel.id)
        channel_ids = bridge.get().json['channels']
        if len(channel_ids) == 2:
            transfer = self.state_persistor.get(event.transfer_id)
            try:
                context = self.ari.channels.getChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_DESTINATION_CONTEXT')['value']
                exten = self.ari.channels.getChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_DESTINATION_EXTEN')['value']
            except ARINotFound:
                logger.error('initiator hung up while creating transfer')

            transfer_state = self.state_factory.make(transfer)
            new_state = transfer_state.start(transfer, context, exten)
            if new_state.transfer.flow == 'blind':
                new_state.complete()

    def recipient_hangup(self, transfer):
        logger.debug('recipient hangup = cancel transfer %s', transfer.id)
        transfer_state = self.state_factory.make(transfer)
        transfer_state.recipient_hangup()

    def initiator_hangup(self, transfer):
        logger.debug('initiator hangup = complete transfer %s', transfer.id)
        transfer_state = self.state_factory.make(transfer)
        transfer_state.initiator_hangup()

    def transferred_hangup(self, transfer):
        logger.debug('transferred hangup = abandon transfer %s', transfer.id)
        transfer_state = self.state_factory.make(transfer)
        transfer_state.transferred_hangup()

    def clean_bridge(self, channel, event):
        try:
            bridge = self.ari.bridges.get(bridgeId=event['bridge']['id'])
        except ARINotFound:
            return
        logger.debug('cleaning bridge %s', bridge.id)
        try:
            self.ari.channels.get(channelId=channel.id)
            channel_is_hungup = False
        except ARINotFound:
            logger.debug('channel who left was hungup')
            channel_is_hungup = True

        if len(bridge.json['channels']) == 1 and channel_is_hungup:
            logger.debug('one channel left in bridge %s', bridge.id)
            lone_channel_id = bridge.json['channels'][0]

            try:
                channel_is_locked = ari_helpers.get_bridge_variable(self.ari, bridge.id, 'XIVO_HANGUP_LOCK_SOURCE')
            except ARINotFound:
                channel_is_locked = False

            if not channel_is_locked:
                logger.debug('emptying bridge %s', bridge.id)
                try:
                    self.ari.channels.hangup(channelId=lone_channel_id)
                except ARINotFound:
                    pass

        try:
            bridge = bridge.get()
        except ARINotFound:
            return
        if len(bridge.json['channels']) == 0:
            logger.debug('destroying bridge %s', bridge.id)
            try:
                bridge.destroy()
            except (ARINotInStasis, ARINotFound):
                pass

    def clean_bridge_variables(self, bridge, event):
        global_variable = 'XIVO_BRIDGE_VARIABLES_{}'.format(bridge.id)
        self.ari.asterisk.setGlobalVar(variable=global_variable, value='')

    def release_hangup_lock(self, channel, event):
        one_lock_source = channel

        try:
            lock_target_id = one_lock_source.getChannelVar(variable='XIVO_HANGUP_LOCK_TARGET')['value']
        except ARINotFound:
            return

        logger.debug('releasing hangup lock from source %s', channel.json['name'])

        for lock_source_candidate in self.ari.channels.list():
            try:
                lock_target_candidate_id = lock_source_candidate.getChannelVar(variable='XIVO_HANGUP_LOCK_TARGET')['value']
            except ARINotFound:
                continue
            if lock_target_candidate_id == lock_target_id:
                try:
                    ari_helpers.unset_variable(self.ari, self.amid, lock_source_candidate.id, 'XIVO_HANGUP_LOCK_TARGET')
                except XiVOAmidUnreachable as e:
                    self.handle_error(e)

        if lock_target_id:
            ari_helpers.set_bridge_variable(self.ari, lock_target_id, 'XIVO_HANGUP_LOCK_SOURCE', '')

    def bypass_hangup_lock_from_source(self, channel, event):
        lock_source = channel
        lock_target_candidate_ids = [bridge.id for bridge in self.ari.bridges.list()
                                     if len(bridge.json['channels']) == 1]
        for lock_target_candidate_id in lock_target_candidate_ids:
            try:
                lock_target_candidate = self.ari.bridges.get(bridgeId=lock_target_candidate_id)
                lock_source_candidate_id = ari_helpers.get_bridge_variable(self.ari, lock_target_candidate_id, 'XIVO_HANGUP_LOCK_SOURCE')
            except ARINotFound:
                continue
            logger.debug('bypassing hangup lock on %s due to source hangup %s', lock_target_candidate.json['name'], channel.json['name'])

            if lock_source_candidate_id == lock_source.id:
                logger.debug('hanging up all channel left in lock target %s', lock_target_candidate_id)
                channel_id = lock_target_candidate.json['channels'][0]
                try:
                    self.ari.channels.hangup(channelId=channel_id)
                except ARINotFound:
                    pass
                try:
                    lock_target_candidate.destroy()
                except ARINotFound:
                    pass

    def bypass_hangup_lock_from_target(self, bridge, event):
        logger.debug('bypassing hangup lock due to target destroy %s', bridge.id)

        lock_target = bridge
        for lock_source_candidate in self.ari.channels.list():
            try:
                lock_target_candidate_id = lock_source_candidate.getChannelVar(variable='XIVO_HANGUP_LOCK_TARGET')['value']
            except ARINotFound:
                continue
            if lock_target_candidate_id == lock_target.id:
                logger.debug('hanging up lock source %s', lock_source_candidate.json['name'])
                try:
                    lock_source_candidate.hangup()
                except ARINotFound:
                    pass
