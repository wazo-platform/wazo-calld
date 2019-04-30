# -*- coding: UTF-8 -*-
# Copyright 2016-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import json
import logging

from ari.exceptions import ARINotFound
from xivo_bus.resources.calls.transfer import CreateTransferEvent

from .transfer import Transfer
logger = logging.getLogger(__name__)


class TransfersBusEventHandler(object):
    def __init__(self, ari, state_factory, state_persistor):
        self._ari = ari
        self._state_factory = state_factory
        self._state_persistor = state_persistor

    def subscribe(self, bus_consumer):
        bus_consumer.on_event('calls.transfer.created', self._start_transfer)

    def _start_transfer(self, event):
        logger.debug('Starting transfer...')
        transfer = Transfer.from_dict(CreateTransferEvent.unmarshal(event).transfer)
        bridge = self._ari.bridges.createWithId(type='mixing', name='transfer', bridgeId=transfer.id)
        bridge.addChannel(channel=transfer.initiator_call)

        try:
            context = self._ari.channels.getChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_RECIPIENT_CONTEXT')['value']
            exten = self._ari.channels.getChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_RECIPIENT_EXTEN')['value']
            variables_str = self._ari.channels.getChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_VARIABLES')['value']
        except ARINotFound:
            logger.error('initiator hung up while creating transfer')

        try:
            variables = json.loads(variables_str)
        except ValueError:
            logger.warning('could not decode transfer variables "%s"', variables_str)
            variables = {}

        transfer_state = self._state_factory.make(transfer)
        new_state = transfer_state.start(transfer, context, exten, variables)
        if new_state.transfer.flow == 'blind':
            new_state.complete()
