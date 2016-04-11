# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from requests import HTTPError
from xivo.pubsub import Pubsub

from xivo_ctid_ng.core.ari_ import not_found

from .event import TransferRecipientCalledEvent
from .event import CreateTransferEvent
from .exceptions import InvalidEvent
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
        self.ari.on_channel_event('StasisStart', self.stasis_start)
        self.stasis_start_pubsub.subscribe('transfer_recipient_called', self.transfer_recipient_called)
        self.stasis_start_pubsub.subscribe('create_transfer', self.create_transfer)
        self.ari.on_channel_event('StasisEnd', self.hangup)
        self.ari.on_channel_event('ChannelLeftBridge', self.clean_bridge)
        self.ari.on_channel_event('ChannelDestroyed', self.hangup)
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
        transfer_bridge = self.ari.bridges.get(bridgeId=event.transfer_bridge)
        transfer_bridge.addChannel(channel=channel.id)

        transfer = self.state_persistor.get(event.transfer_bridge)
        transfer.recipient_call = channel.id
        transfer.status = TransferStatus.answered
        self.state_persistor.upsert(transfer)

    def create_transfer(self, (channel, event)):
        event = CreateTransferEvent(event)
        candidates = [candidate for candidate in self.ari.bridges.list() if candidate.id == event.transfer_id]
        if not candidates:
            bridge = self.ari.bridges.createWithId(type='mixing', name='transfer', bridgeId=event.transfer_id)
        else:
            bridge = candidates[0]

        bridge.addChannel(channel=channel.id)
        channel_ids = self.ari.bridges.get(bridgeId=bridge.id).json['channels']
        if len(channel_ids) == 2:
            transfer = self.state_persistor.get(event.transfer_id)
            transferred_call = transfer.transferred_call
            initiator_call = transfer.initiator_call
            context = self.ari.channels.getChannelVar(channelId=initiator_call, variable='XIVO_TRANSFER_DESTINATION_CONTEXT')['value']
            exten = self.ari.channels.getChannelVar(channelId=initiator_call, variable='XIVO_TRANSFER_DESTINATION_EXTEN')['value']
            self.services.hold_transferred_call(transferred_call)
            transfer.recipient_call = self.services.originate_recipient(initiator_call, context, exten, event.transfer_id)
            self.state_persistor.upsert(transfer)

    def recipient_hangup(self, transfer):
        self.services.cancel(transfer.id)

    def initiator_hangup(self, transfer):
        self.services.complete(transfer.id)

    def transferred_hangup(self, transfer):
        self.services.abandon(transfer.id)

    def clean_bridge(self, channel, event):
        try:
            bridge = self.ari.bridges.get(bridgeId=event['bridge']['id'])
        except HTTPError as e:
            if not_found(e):
                return
            raise
        logger.debug('cleaning bridge %s', bridge.id)
        try:
            self.ari.channels.get(channelId=channel.id)
            channel_is_hungup = False
        except HTTPError as e:
            if not_found(e):
                channel_is_hungup = True
            else:
                raise

        if len(bridge.json['channels']) == 1 and channel_is_hungup:
            logger.debug('emptying bridge %s', bridge.id)
            lone_channel_id = bridge.json['channels'][0]
            self.ari.channels.hangup(channelId=lone_channel_id)

        bridge = bridge.get()
        if len(bridge.json['channels']) == 0:
            logger.debug('destroying bridge %s', bridge.id)
            bridge.destroy()
