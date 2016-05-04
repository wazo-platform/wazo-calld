# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
import uuid

from ari.exceptions import ARINotFound

from .exceptions import TransferAnswerError
from .exceptions import TransferCreationError
from .exceptions import TransferCancellationError
from .exceptions import TransferCompletionError
from .transfer import Transfer, TransferStatus

logger = logging.getLogger(__name__)


class StateFactory(object):

    def __init__(self, ari=None):
        self._state_constructors = {}
        self._ari = ari

    def set_dependencies(self, ari, services):
        self._ari = ari
        self._services = services

    def make(self, transfer):
        if not self._ari or not self._services:
            raise RuntimeError('StateFactory is not configured')
        return self._state_constructors[transfer.status](self._ari, self._services, transfer)

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
        return self

    def initiator_hangup(self):
        return self

    def recipient_hangup(self):
        return self

    def recipient_answer(self):
        return self

    def create(self):
        return self

    def start(self):
        return self

    def complete(self):
        return self

    def cancel(self):
        return self

    def _abandon(self):
        self._services.unset_variable(self.transfer.recipient_call, 'XIVO_TRANSFER_ID')
        self._services.unset_variable(self.transfer.recipient_call, 'XIVO_TRANSFER_ROLE')
        self._services.unset_variable(self.transfer.initiator_call, 'XIVO_TRANSFER_ID')
        self._services.unset_variable(self.transfer.initiator_call, 'XIVO_TRANSFER_ROLE')

        if self.transfer.transferred_call:
            try:
                self._ari.channels.hangup(channelId=self.transfer.transferred_call)
            except ARINotFound:
                pass

    def _cancel(self):
        self._services.unset_variable(self.transfer.transferred_call, 'XIVO_TRANSFER_ID')
        self._services.unset_variable(self.transfer.transferred_call, 'XIVO_TRANSFER_ROLE')
        self._services.unset_variable(self.transfer.initiator_call, 'XIVO_TRANSFER_ID')
        self._services.unset_variable(self.transfer.initiator_call, 'XIVO_TRANSFER_ROLE')

        if self.transfer.recipient_call:
            try:
                self._ari.channels.hangup(channelId=self.transfer.recipient_call)
            except ARINotFound:
                pass

        try:
            self._services.unhold_transferred_call(self.transfer.transferred_call)
        except ARINotFound:
            raise TransferCancellationError(self.transfer.id, 'transferred hung up')

        try:
            self._services.unring_initiator_call(self.transfer.initiator_call)
        except ARINotFound:
            raise TransferCancellationError(self.transfer.id, 'initiator hung up')

    @classmethod
    def from_state(cls, other_state):
        return cls(other_state._ari, other_state._services, other_state.transfer)


@state_factory.state
class TransferStateReadyStasis(TransferState):

    name = 'ready'

    def create(self, transferred_channel, initiator_channel, context, exten, flow):
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
        self.transfer.flow = flow

        return TransferStateRingback.from_state(self)


@state_factory.state
class TransferStateReadyNonStasis(TransferState):

    name = 'ready_non_stasis'

    def create(self, transferred_channel, initiator_channel, context, exten, flow):
        transfer_id = str(uuid.uuid4())
        self._services.convert_transfer_to_stasis(transferred_channel.id, initiator_channel.id, context, exten, transfer_id)
        self.transfer = Transfer(transfer_id)
        self.transfer.initiator_call = initiator_channel.id
        self.transfer.transferred_call = transferred_channel.id
        self.transfer.status = TransferStatus.starting
        self.transfer.flow = flow

        return TransferStateStarting.from_state(self)


@state_factory.state
class TransferStateStarting(TransferState):

    name = 'starting'

    def start(self, transfer, context, exten):
        self.transfer = transfer

        try:
            self._services.hold_transferred_call(self.transfer.transferred_call)
        except ARINotFound:
            pass

        try:
            self._ari.channels.ring(channelId=self.transfer.initiator_call)
        except ARINotFound:
            logger.error('initiator hung up while creating transfer')

        try:
            self.transfer.recipient_call = self._services.originate_recipient(self.transfer.initiator_call,
                                                                              context,
                                                                              exten,
                                                                              self.transfer.id)
        except TransferCreationError as e:
            logger.error(e.message, e.details)

        self.transfer.status = TransferStatus.ringback

        return TransferStateRingback.from_state(self)


@state_factory.state
class TransferStateRingback(TransferState):

    name = 'ringback'

    def transferred_hangup(self):
        self._abandon()
        return TransferStateReadyStasis.from_state(self)

    def initiator_hangup(self):
        try:
            self._services.unhold_transferred_call(self.transfer.transferred_call)
            self._ari.channels.ring(channelId=self.transfer.transferred_call)
        except ARINotFound:
            raise TransferCompletionError(self.transfer.id, 'transferred hung up')

        self.transfer.status = 'blind_transferred'

        return TransferStateBlindTransferred.from_state(self)

    def recipient_hangup(self):
        return self.cancel()

    def complete(self):
        try:
            self._ari.channels.hangup(channelId=self.transfer.initiator_call)
        except ARINotFound:
            pass

        try:
            self._services.unhold_transferred_call(self.transfer.transferred_call)
            self._ari.channels.ring(channelId=self.transfer.transferred_call)
        except ARINotFound:
            raise TransferCompletionError(self.transfer.id, 'transferred hung up')

        self.transfer.status = 'blind_transferred'

        return TransferStateBlindTransferred.from_state(self)

    def cancel(self):
        self._cancel()
        return TransferStateReadyStasis.from_state(self)

    def recipient_answer(self):
        try:
            self._services.unring_initiator_call(self.transfer.initiator_call)
        except ARINotFound:
            raise TransferAnswerError(self.transfer.id, 'initiator hung up')
        self.transfer.status = TransferStatus.answered

        return TransferStateAnswered.from_state(self)


@state_factory.state
class TransferStateAnswered(TransferState):

    name = 'answered'

    def transferred_hangup(self):
        self._abandon()
        return TransferStateReadyStasis.from_state(self)

    def initiator_hangup(self):
        self._services.unset_variable(self.transfer.transferred_call, 'XIVO_TRANSFER_ID')
        self._services.unset_variable(self.transfer.transferred_call, 'XIVO_TRANSFER_ROLE')
        self._services.unset_variable(self.transfer.recipient_call, 'XIVO_TRANSFER_ID')
        self._services.unset_variable(self.transfer.recipient_call, 'XIVO_TRANSFER_ROLE')

        try:
            self._services.unhold_transferred_call(self.transfer.transferred_call)
        except ARINotFound:
            raise TransferCompletionError(self.transfer.id, 'transferred hung up')

        self.transfer.status = 'ready'

        return TransferStateReadyStasis.from_state(self)

    def recipient_hangup(self):
        return self.cancel()

    def complete(self):
        self._services.unset_variable(self.transfer.transferred_call, 'XIVO_TRANSFER_ID')
        self._services.unset_variable(self.transfer.transferred_call, 'XIVO_TRANSFER_ROLE')
        self._services.unset_variable(self.transfer.recipient_call, 'XIVO_TRANSFER_ID')
        self._services.unset_variable(self.transfer.recipient_call, 'XIVO_TRANSFER_ROLE')

        try:
            self._ari.channels.hangup(channelId=self.transfer.initiator_call)
        except ARINotFound:
            pass

        try:
            self._services.unhold_transferred_call(self.transfer.transferred_call)
        except ARINotFound:
            raise TransferCompletionError(self.transfer.id, 'transferred hung up')

        self.transfer.status = 'ready'

        return TransferStateReadyStasis.from_state(self)

    def cancel(self):
        self._cancel()
        return TransferStateReadyStasis.from_state(self)


@state_factory.state
class TransferStateBlindTransferred(TransferState):

    name = 'blind_transferred'

    def recipient_answer(self):
        self._services.unset_variable(self.transfer.transferred_call, 'XIVO_TRANSFER_ID')
        self._services.unset_variable(self.transfer.transferred_call, 'XIVO_TRANSFER_ROLE')
        self._services.unset_variable(self.transfer.recipient_call, 'XIVO_TRANSFER_ID')
        self._services.unset_variable(self.transfer.recipient_call, 'XIVO_TRANSFER_ROLE')

        try:
            self._services.unring_initiator_call(self.transfer.transferred_call)
        except ARINotFound:
            raise TransferAnswerError(self.transfer.id, 'transferred hung up')

        self.transfer.status = 'ready'

        return TransferStateReadyStasis.from_state(self)
