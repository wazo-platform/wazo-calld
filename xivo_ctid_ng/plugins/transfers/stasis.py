# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo.pubsub import Pubsub

from .event import TransferRecipientCalledEvent
from .event import CreateTransferEvent
from .exceptions import InvalidTransferRecipientCalledEvent
from .exceptions import InvalidCreateTransferEvent

logger = logging.getLogger(__name__)


class TransfersStasis(object):

    def __init__(self, ari_client, services, xivo_uuid):
        self.ari = ari_client
        self.services = services
        self.xivo_uuid = xivo_uuid
        self.stasis_start_pubsub = Pubsub()

    def subscribe(self):
        self.ari.on_channel_event('StasisStart', self.stasis_start)
        self.stasis_start_pubsub.subscribe('transfer_recipient_called', self.transfer_recipient_called)
        self.stasis_start_pubsub.subscribe('create_transfer', self.create_transfer)

    def stasis_start(self, event_objects, event):
        channel = event_objects['channel']
        try:
            app_action = event['args'][1]
        except (IndexError):
            return
        self.stasis_start_pubsub.publish(app_action, (channel, event))

    def transfer_recipient_called(self, (channel, event)):
        try:
            event = TransferRecipientCalledEvent(event)
        except InvalidTransferRecipientCalledEvent:
            logger.error('invalid stasis event received: %s', event)
            return
        transfer_bridge = self.ari.bridges.get(bridgeId=event.transfer_bridge)
        transfer_bridge.addChannel(channel=channel.id)

    def create_transfer(self, (channel, event)):
        try:
            event = CreateTransferEvent(event)
        except InvalidCreateTransferEvent:
            logger.error('invalid stasis event received: %s', event)
            return

        candidates = [candidate for candidate in self.ari.bridges.list() if candidate.id == event.transfer_id]
        if not candidates:
            bridge = self.ari.bridges.createWithId(type='mixing', name='transfer', bridgeId=event.transfer_id)
        else:
            bridge = candidates[0]

        bridge.addChannel(channel=channel.id)
        bridge = self.ari.bridges.get(bridgeId=bridge.id)
        if len(bridge.json['channels']) == 2:
            channel_role = [(channel_id, self.ari.channels.getChannelVar(channelId=channel_id, variable='XIVO_TRANSFER')['value'])
                            for channel_id in bridge.json['channels']]
            transferred_call = next(channel_id for (channel_id, transfer_role) in channel_role if transfer_role == 'transferred')
            initiator_call = next(channel_id for (channel_id, transfer_role) in channel_role if transfer_role == 'initiator')
            context = self.ari.channels.getChannelVar(channelId=initiator_call, variable='XIVO_TRANSFER_DESTINATION_CONTEXT')['value']
            exten = self.ari.channels.getChannelVar(channelId=initiator_call, variable='XIVO_TRANSFER_DESTINATION_EXTEN')['value']
            self.services.create_transfer_with_bridge(transferred_call, initiator_call, context, exten, bridge)
