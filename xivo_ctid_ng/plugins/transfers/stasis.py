# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo.pubsub import Pubsub

from .event import TransferRecipientCalledEvent
from .event import CreateTransferEvent
from .exceptions import InvalidEvent

logger = logging.getLogger(__name__)


class TransfersStasis(object):

    def __init__(self, ari_client, services, xivo_uuid):
        self.ari = ari_client
        self.services = services
        self.xivo_uuid = xivo_uuid
        self.stasis_start_pubsub = Pubsub()
        self.stasis_start_pubsub.set_exception_handler(self.invalid_event)

    def subscribe(self):
        self.ari.on_channel_event('StasisStart', self.stasis_start)
        self.stasis_start_pubsub.subscribe('transfer_recipient_called', self.transfer_recipient_called)
        self.stasis_start_pubsub.subscribe('create_transfer', self.create_transfer)

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

    def transfer_recipient_called(self, (channel, event)):
        event = TransferRecipientCalledEvent(event)
        transfer_bridge = self.ari.bridges.get(bridgeId=event.transfer_bridge)
        transfer_bridge.addChannel(channel=channel.id)

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
            channel_role = [(channel_id, self.ari.channels.getChannelVar(channelId=channel_id, variable='XIVO_TRANSFER_ROLE')['value'])
                            for channel_id in channel_ids]
            transferred_call = next(channel_id for (channel_id, transfer_role) in channel_role if transfer_role == 'transferred')
            initiator_call = next(channel_id for (channel_id, transfer_role) in channel_role if transfer_role == 'initiator')
            context = self.ari.channels.getChannelVar(channelId=initiator_call, variable='XIVO_TRANSFER_DESTINATION_CONTEXT')['value']
            exten = self.ari.channels.getChannelVar(channelId=initiator_call, variable='XIVO_TRANSFER_DESTINATION_EXTEN')['value']
            self.services.hold_transferred_call(transferred_call)
            self.services.originate_recipient(initiator_call, context, exten, event.transfer_id)
