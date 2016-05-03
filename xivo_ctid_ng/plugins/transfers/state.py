# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
import uuid

from ari.exceptions import ARINotFound

from .exceptions import TransferCreationError
from .transfer import Transfer, TransferStatus

logger = logging.getLogger(__name__)


class StateFactory(object):

    def __init__(self, ari=None):
        self._state_constructors = {}
        self._ari = ari

    def set_dependencies(self, ari):
        self._ari = ari

    def make(self, state_name):
        if not self._ari:
            raise RuntimeError('StateFactory is not configured')
        return self._state_constructors[state_name](self._ari, self._stat_sender)

    def state(self, wrapped_class):
        self._state_constructors[wrapped_class.name] = wrapped_class
        return wrapped_class


state_factory = StateFactory()


class TransferState(object):

    def __init__(self, ari, services, transfer=None):
        self._ari = ari
        self._services = services
        self.transfer = transfer

    def transferred_hangup(self):
        pass

    def initiator_hangup(self):
        pass

    def recipient_hangup(self):
        pass

    def recipient_answer(self):
        pass

    def create(self):
        pass

    def start(self):
        pass

    def complete(self):
        pass

    def cancel(self):
        pass

    @classmethod
    def from_state(cls, other_state):
        return cls(other_state._ari, other_state._services, other_state.transfer)


@state_factory.state
class TransferStateReadyStasis(TransferState):

    name = 'ready_stasis'

    def create(self, transferred_channel, initiator_channel, context, exten):
        transfer_bridge = self._ari.bridges.create(type='mixing', name='transfer')
        transfer_id = transfer_bridge.id
        try:
            transferred_channel.setChannelVar(variable='XIVO_TRANSFER_ROLE', value='transferred')
            transferred_channel.setChannelVar(variable='XIVO_TRANSFER_ID', value=transfer_id)
            initiator_channel.setChannelVar(variable='XIVO_TRANSFER_ROLE', value='initiator')
            initiator_channel.setChannelVar(variable='XIVO_TRANSFER_ID', value=transfer_id)
            transfer_bridge.addChannel(channel=transferred_channel.id)
            transfer_bridge.addChannel(channel=initiator_channel.id)
        except ARINotFound:
            raise TransferCreationError('some channel got hung up')

        try:
            self._services.hold_transferred_call(transferred_channel.id)
        except ARINotFound:
            raise TransferCreationError('transferred call hung up')

        try:
            self._ari.channels.ring(channelId=initiator_channel.id)
        except ARINotFound:
            raise TransferCreationError('initiator call hung up')

        recipient_call = self._services.originate_recipient(initiator_channel.id, context, exten, transfer_id)

        self.transfer = Transfer(transfer_id)
        self.transfer.transferred_call = transferred_channel.id
        self.transfer.initiator_call = initiator_channel.id
        self.transfer.recipient_call = recipient_call
        self.transfer.status = TransferStatus.ringback

        return TransferStateRingback.from_state(self)


@state_factory.state
class TransferStateReadyNonStasis(TransferState):

    name = 'ready_non_stasis'

    def create(self, transferred_channel, initiator_channel, context, exten):
        transfer_id = str(uuid.uuid4())
        self._services.convert_transfer_to_stasis(transferred_channel.id, initiator_channel.id, context, exten, transfer_id)
        self.transfer = Transfer(transfer_id)
        self.transfer.initiator_call = initiator_channel.id
        self.transfer.transferred_call = transferred_channel.id
        self.transfer.status = TransferStatus.starting

        return TransferStateStarting.from_state(self)


@state_factory.state
class TransferStateStarting(TransferState):

    name = 'starting'

    def start(self):
        return TransferStateRingback.from_state(self)


@state_factory.state
class TransferStateRingback(TransferState):

    name = 'ringback'

    def transferred_hangup(self):
        return TransferStateReadyStasis.from_state(self)

    def recipient_hangup(self):
        return self.cancel()

    def cancel(self):
        return TransferStateReadyStasis.from_state(self)

    def recipient_answer(self):
        return TransferStateAnswered.from_state(self)


@state_factory.state
class TransferStateAnswered(TransferState):

    name = 'answered'

    def transferred_hangup(self):
        return TransferStateReadyStasis.from_state(self)

    def initiator_hangup(self):
        return self.complete()

    def recipient_hangup(self):
        return self.cancel()

    def complete(self):
        return TransferStateReadyStasis.from_state(self)

    def cancel(self):
        return TransferStateReadyStasis.from_state(self)
