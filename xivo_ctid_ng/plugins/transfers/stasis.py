# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo.pubsub import Pubsub

from ari.exceptions import ARINotFound
from ari.exceptions import ARINotInStasis

from .event import TransferRecipientAnsweredEvent
from .event import CreateTransferEvent
from .exceptions import InvalidEvent
from .exceptions import TransferCreationError
from .exceptions import TransferCancellationError
from .exceptions import TransferCompletionError
from .transfer import TransferStatus, TransferRole

logger = logging.getLogger(__name__)


class TransfersStasis(object):

    def __init__(self, ari_client, services, state_persistor, xivo_uuid):
        self.ari = ari_client
        self.services = services
        self.xivo_uuid = xivo_uuid
        self.stasis_start_pubsub = Pubsub()
        self.stasis_start_pubsub.set_exception_handler(self.invalid_event)
        self.hangup_pubsub = Pubsub()
        self.hangup_pubsub.set_exception_handler(self.invalid_event)
        self.state_persistor = state_persistor

    def subscribe(self):
        self.ari.on_channel_event('ChannelEnteredBridge', self.release_hangup_lock)
        self.ari.on_channel_event('ChannelDestroyed', self.bypass_hangup_lock_from_source)
        self.ari.on_channel_event('ChannelDestroyed', self.bypass_hangup_lock_from_target)

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
        else:
            raise

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
            self.services.unset_variable(channel.id, 'XIVO_TRANSFER_ID')
            self.services.unset_variable(channel.id, 'XIVO_TRANSFER_ROLE')

            for channel_id in transfer_bridge.json['channels']:
                try:
                    self.services.unring_initiator_call(channel_id)
                except ARINotFound:
                    pass
        else:
            logger.debug('recipient answered, transfer continues normally')
            try:
                self.services.unring_initiator_call(transfer.initiator_call)
            except ARINotFound:
                pass
            transfer.recipient_call = channel.id
            transfer.status = TransferStatus.answered
            self.state_persistor.upsert(transfer)

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
            transferred_call = transfer.transferred_call
            initiator_call = transfer.initiator_call
            try:
                context = self.ari.channels.getChannelVar(channelId=initiator_call, variable='XIVO_TRANSFER_DESTINATION_CONTEXT')['value']
                exten = self.ari.channels.getChannelVar(channelId=initiator_call, variable='XIVO_TRANSFER_DESTINATION_EXTEN')['value']
            except ARINotFound:
                logger.error('initiator hung up while creating transfer')

            try:
                self.services.hold_transferred_call(transferred_call)
            except ARINotFound:
                pass

            try:
                self.ari.channels.ring(channelId=initiator_call)
            except ARINotFound:
                logger.error('initiator hung up while creating transfer')

            try:
                transfer.recipient_call = self.services.originate_recipient(initiator_call, context, exten, event.transfer_id)
            except TransferCreationError as e:
                logger.error(e.message, e.details)

            self.state_persistor.upsert(transfer)

    def recipient_hangup(self, transfer):
        logger.debug('recipient hangup = cancel transfer %s', transfer.id)
        try:
            self.services.cancel(transfer.id)
        except TransferCancellationError as e:
            logger.error(e.message, e.details)

    def initiator_hangup(self, transfer):
        logger.debug('initiator hangup = complete transfer %s', transfer.id)
        try:
            self.services.complete(transfer.id)
        except TransferCompletionError as e:
            logger.error(e.message, e.details)

    def transferred_hangup(self, transfer):
        logger.debug('transferred hangup = abandon transfer %s', transfer.id)
        self.services.abandon(transfer.id)

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
                channel_is_locked = self.ari.channels.getChannelVar(channelId=lone_channel_id, variable='XIVO_HANGUP_LOCK_SOURCE')['value']
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
            except ARINotInStasis:
                pass

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
                self.services.unset_variable(lock_source_candidate.id, 'XIVO_HANGUP_LOCK_TARGET')

        if lock_target_id:
            self.services.unset_variable(lock_target_id, 'XIVO_HANGUP_LOCK_SOURCE')

    def bypass_hangup_lock_from_source(self, channel, event):
        lock_source = channel
        lone_channel_ids = [bridge.json['channels'][0] for bridge in self.ari.bridges.list()
                            if len(bridge.json['channels']) == 1]
        for lock_target_candidate_id in lone_channel_ids:
            try:
                lock_target_candidate = self.ari.channels.get(channelId=lock_target_candidate_id)
                lock_source_candidate_id = lock_target_candidate.getChannelVar(variable='XIVO_HANGUP_LOCK_SOURCE')['value']
            except ARINotFound:
                continue
            logger.debug('bypassing hangup lock on %s due to source hangup %s', lock_target_candidate.json['name'], channel.json['name'])

            if lock_source_candidate_id == lock_source.id:
                logger.debug('hanging up lock target %s', lock_target_candidate.json['name'])
                try:
                    lock_target_candidate.hangup()
                except ARINotFound:
                    pass

    def bypass_hangup_lock_from_target(self, channel, event):
        logger.debug('bypassing hangup lock due to target hangup %s', channel.json['name'])

        lock_target = channel
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
