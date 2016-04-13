# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo.pubsub import Pubsub

from xivo_ctid_ng.core.exceptions import ARINotFound
from xivo_ctid_ng.core.ari.exceptions import ARINotInStasis

from .event import TransferRecipientCalledEvent
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
        self.ari.on_channel_event('ChannelDestroyed', self.kill_hangup_lock)

        self.ari.on_channel_event('ChannelLeftBridge', self.clean_bridge)

        self.ari.on_channel_event('StasisStart', self.stasis_start)
        self.stasis_start_pubsub.subscribe('transfer_recipient_called', self.transfer_recipient_called)
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
            logger.debug('ignoring StasisStart event: %s', event)
            return
        self.stasis_start_pubsub.publish(app_action, (channel, event))

    def hangup(self, channel, event):
        try:
            transfer = self.state_persistor.get_by_channel(channel.id)
        except KeyError:
            logger.debug('ignoring StasisEnd event: %s', event)
            return
        transfer_role = transfer.role(channel.id)
        self.hangup_pubsub.publish(transfer_role, transfer)

    def transfer_recipient_called(self, (channel, event)):
        event = TransferRecipientCalledEvent(event)
        try:
            transfer_bridge = self.ari.bridges.get(bridgeId=event.transfer_bridge)
            transfer_bridge.addChannel(channel=channel.id)
        except ARINotFound:
            logger.error('recipient answered, but transfer was hung up')

        try:
            transfer = self.state_persistor.get(event.transfer_bridge)
        except KeyError:
            logger.debug('recipient answered, but transfer was abandoned')
            channel.setChannelVar(variable='XIVO_TRANSFER_ID', value='')
            channel.setChannelVar(variable='XIVO_TRANSFER_ROLE', value='')
        else:
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
        logger.debug('releasing hangup lock')
        lock_source = channel

        try:
            lock_target_id = lock_source.getChannelVar(variable='XIVO_HANGUP_LOCK_TARGET')['value']
        except ARINotFound:
            return

        try:
            lock_source.setChannelVar(variable='XIVO_HANGUP_LOCK_TARGET', value='')
        except ARINotFound:
            pass

        try:
            lock_target = self.ari.channels.get(channelId=lock_target_id)
            lock_target.setChannelVar(variable='XIVO_HANGUP_LOCK_SOURCE', value='')
        except ARINotFound:
            return

    def kill_hangup_lock(self, channel, event):
        logger.debug('killing hangup lock')
        lock_source = channel
        lock_source_to_target = {}
        for bridge in self.ari.bridges.list():
            if len(bridge.json['channels']) == 1:
                lock_target_candidate_id = bridge.json['channels'][0]
                try:
                    lock_target_candidate = self.ari.channels.get(channelId=lock_target_candidate_id)
                    lock_source_candidate_id = lock_target_candidate.getChannelVar(variable='XIVO_HANGUP_LOCK_SOURCE')['value']
                    lock_source_to_target[lock_source_candidate_id] = lock_target_candidate
                except ARINotFound:
                    continue

        lock_target = lock_source_to_target.get(lock_source.id)
        if lock_target:
            logger.debug('hanging up lock target %s', lock_target.id)
            try:
                lock_target.hangup()
            except ARINotFound:
                pass
