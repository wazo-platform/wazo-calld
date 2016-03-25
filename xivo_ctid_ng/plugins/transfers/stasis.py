# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo.pubsub import Pubsub

from .event import TransferRecipientCalledEvent
from .exceptions import InvalidTransferRecipientCalledEvent
# from .state import state_factory

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
        pretransfer_bridge = self.ari.bridges.create(type='mixing')
        pretransfer_bridge.addChannel(channel=event.initiator_call)
        pretransfer_bridge.addChannel(channel=channel.id)
