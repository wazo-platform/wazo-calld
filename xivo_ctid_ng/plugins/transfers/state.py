# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
import uuid

from ari.exceptions import ARINotFound

from . import ami_helpers
from . import ari_helpers
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
        self._configured = False

    def set_dependencies(self, *dependencies):
        self._dependencies = dependencies
        self._configured = True

    def make(self, transfer):
        if not self._configured:
            raise RuntimeError('StateFactory is not configured')
        dependencies = list(self._dependencies) + [transfer]
        return self._state_constructors[transfer.status](*dependencies)

    def make_from_class(self, state_class):
        if not self._configured:
            raise RuntimeError('StateFactory is not configured')
        dependencies = list(self._dependencies)
        return state_class(*dependencies)

    def state(self, wrapped_class):
        self._state_constructors[wrapped_class.name] = wrapped_class
        return wrapped_class


state_factory = StateFactory()


def transition(decorated):
    def decorator(*args, **kwargs):
        result = decorated(*args, **kwargs)
        result.update_cache()
        return result
    return decorator


class TransferState(object):

    def __init__(self, amid, ari, notifier, services, state_persistor, transfer=None):
        self._amid = amid
        self._ari = ari
        self._notifier = notifier
        self._services = services
        self._state_persistor = state_persistor
        self.transfer = transfer

    @classmethod
    def from_state(cls, other_state):
        new_state = cls(other_state._amid,
                        other_state._ari,
                        other_state._notifier,
                        other_state._services,
                        other_state._state_persistor,
                        other_state.transfer)
        new_state.transfer.status = new_state.name
        return new_state

    @transition
    def transferred_hangup(self):
        raise NotImplementedError(self.name)

    @transition
    def initiator_hangup(self):
        raise NotImplementedError(self.name)

    @transition
    def recipient_hangup(self):
        raise NotImplementedError(self.name)

    @transition
    def recipient_answer(self):
        raise NotImplementedError(self.name)

    @transition
    def create(self):
        raise NotImplementedError(self.name)

    @transition
    def start(self):
        raise NotImplementedError(self.name)

    @transition
    def complete(self):
        raise NotImplementedError(self.name)

    @transition
    def cancel(self):
        raise NotImplementedError(self.name)

    def update_cache(self):
        raise NotImplementedError()

    def _abandon(self):
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.recipient_call, 'XIVO_TRANSFER_ID')
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.recipient_call, 'XIVO_TRANSFER_ROLE')
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.initiator_call, 'XIVO_TRANSFER_ID')
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.initiator_call, 'XIVO_TRANSFER_ROLE')

        if self.transfer.transferred_call:
            try:
                self._ari.channels.hangup(channelId=self.transfer.transferred_call)
            except ARINotFound:
                pass

        self._notifier.abandoned(self.transfer)

    def _cancel(self):
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.transferred_call, 'XIVO_TRANSFER_ID')
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.transferred_call, 'XIVO_TRANSFER_ROLE')
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.initiator_call, 'XIVO_TRANSFER_ID')
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.initiator_call, 'XIVO_TRANSFER_ROLE')

        if self.transfer.recipient_call:
            try:
                self._ari.channels.hangup(channelId=self.transfer.recipient_call)
            except ARINotFound:
                pass

        try:
            ari_helpers.unhold_transferred_call(self._ari, self.transfer.transferred_call)
        except ARINotFound:
            raise TransferCancellationError(self.transfer.id, 'transferred hung up')

        try:
            ari_helpers.unring_initiator_call(self._ari, self.transfer.initiator_call)
        except ARINotFound:
            raise TransferCancellationError(self.transfer.id, 'initiator hung up')

        self._notifier.cancelled(self.transfer)


@state_factory.state
class TransferStateReady(TransferState):

    name = TransferStatus.ready

    @transition
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
            ari_helpers.hold_transferred_call(self._ari, transferred_channel.id)
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
        self.transfer.status = self.name
        self._notifier.created(self.transfer)

        return TransferStateRingback.from_state(self)

    def from_state(self, other_state):
        raise NotImplementedError('This state cannot be transitioned to')


@state_factory.state
class TransferStateReadyNonStasis(TransferState):

    name = 'ready_non_stasis'

    @transition
    def create(self, transferred_channel, initiator_channel, context, exten):
        transfer_id = str(uuid.uuid4())
        ami_helpers.convert_transfer_to_stasis(self._amid,
                                               transferred_channel.id,
                                               initiator_channel.id,
                                               context,
                                               exten,
                                               transfer_id)
        self.transfer = Transfer(transfer_id)
        self.transfer.initiator_call = initiator_channel.id
        self.transfer.transferred_call = transferred_channel.id
        self.transfer.status = self.name
        self._notifier.created(self.transfer)

        return TransferStateStarting.from_state(self)

    def from_state(self, other_state):
        raise NotImplementedError('This state cannot be transitioned to')


@state_factory.state
class TransferStateStarting(TransferState):

    name = TransferStatus.starting

    @transition
    def start(self, transfer, context, exten):
        self.transfer = transfer

        try:
            ari_helpers.hold_transferred_call(self._ari, self.transfer.transferred_call)
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

        return TransferStateRingback.from_state(self)

    @transition
    def complete(self):
        self.transfer.flow = 'blind'

        return self

    def update_cache(self):
        self._state_persistor.upsert(self.transfer)


@state_factory.state
class TransferStateRingback(TransferState):

    name = TransferStatus.ringback

    @transition
    def transferred_hangup(self):
        self._abandon()
        return TransferStateEnded.from_state(self)

    @transition
    def initiator_hangup(self):
        try:
            ari_helpers.unhold_transferred_call(self._ari, self.transfer.transferred_call)
            self._ari.channels.ring(channelId=self.transfer.transferred_call)
        except ARINotFound:
            raise TransferCompletionError(self.transfer.id, 'transferred hung up')

        self.transfer.flow = 'blind'
        self._notifier.completed(self.transfer)

        return TransferStateBlindTransferred.from_state(self)

    @transition
    def recipient_hangup(self):
        return self.cancel()

    @transition
    def complete(self):
        try:
            self._ari.channels.hangup(channelId=self.transfer.initiator_call)
        except ARINotFound:
            pass

        try:
            ari_helpers.unhold_transferred_call(self._ari, self.transfer.transferred_call)
            self._ari.channels.ring(channelId=self.transfer.transferred_call)
        except ARINotFound:
            raise TransferCompletionError(self.transfer.id, 'transferred hung up')

        self.transfer.flow = 'blind'
        self._notifier.completed(self.transfer)

        return TransferStateBlindTransferred.from_state(self)

    @transition
    def cancel(self):
        self._cancel()
        return TransferStateEnded.from_state(self)

    @transition
    def recipient_answer(self):
        try:
            ari_helpers.unring_initiator_call(self._ari, self.transfer.initiator_call)
        except ARINotFound:
            raise TransferAnswerError(self.transfer.id, 'initiator hung up')

        return TransferStateAnswered.from_state(self)

    def update_cache(self):
        self._state_persistor.upsert(self.transfer)


@state_factory.state
class TransferStateBlindTransferred(TransferState):

    name = TransferStatus.blind_transferred

    @transition
    def transferred_hangup(self):
        return TransferStateEnded.from_state(self)

    @transition
    def initiator_hangup(self):
        return self

    @transition
    def recipient_hangup(self):
        return TransferStateEnded.from_state(self)

    @transition
    def recipient_answer(self):
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.transferred_call, 'XIVO_TRANSFER_ID')
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.transferred_call, 'XIVO_TRANSFER_ROLE')
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.recipient_call, 'XIVO_TRANSFER_ID')
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.recipient_call, 'XIVO_TRANSFER_ROLE')

        try:
            ari_helpers.unring_initiator_call(self._ari, self.transfer.transferred_call)
        except ARINotFound:
            raise TransferAnswerError(self.transfer.id, 'transferred hung up')

        self._notifier.answered(self.transfer)

        return TransferStateEnded.from_state(self)

    def update_cache(self):
        self._state_persistor.upsert(self.transfer)


@state_factory.state
class TransferStateAnswered(TransferState):

    name = TransferStatus.answered

    @transition
    def transferred_hangup(self):
        self._abandon()
        return TransferStateEnded.from_state(self)

    @transition
    def initiator_hangup(self):
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.transferred_call, 'XIVO_TRANSFER_ID')
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.transferred_call, 'XIVO_TRANSFER_ROLE')
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.recipient_call, 'XIVO_TRANSFER_ID')
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.recipient_call, 'XIVO_TRANSFER_ROLE')

        try:
            ari_helpers.unhold_transferred_call(self._ari, self.transfer.transferred_call)
        except ARINotFound:
            raise TransferCompletionError(self.transfer.id, 'transferred hung up')

        self._notifier.completed(self.transfer)

        return TransferStateEnded.from_state(self)

    @transition
    def recipient_hangup(self):
        return self.cancel()

    @transition
    def complete(self):
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.transferred_call, 'XIVO_TRANSFER_ID')
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.transferred_call, 'XIVO_TRANSFER_ROLE')
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.recipient_call, 'XIVO_TRANSFER_ID')
        ari_helpers.unset_variable(self._ari, self._amid, self.transfer.recipient_call, 'XIVO_TRANSFER_ROLE')

        try:
            self._ari.channels.hangup(channelId=self.transfer.initiator_call)
        except ARINotFound:
            pass

        try:
            ari_helpers.unhold_transferred_call(self._ari, self.transfer.transferred_call)
        except ARINotFound:
            raise TransferCompletionError(self.transfer.id, 'transferred hung up')

        self._notifier.completed(self.transfer)

        return TransferStateEnded.from_state(self)

    @transition
    def cancel(self):
        self._cancel()
        return TransferStateEnded.from_state(self)

    def update_cache(self):
        self._state_persistor.upsert(self.transfer)

    @classmethod
    def from_state(cls, *args, **kwargs):
        new_state = super(TransferStateAnswered, cls).from_state(*args, **kwargs)
        new_state._notifier.answered(new_state.transfer)
        return new_state


@state_factory.state
class TransferStateEnded(TransferState):

    name = 'ended'

    def update_cache(self):
        self._state_persistor.remove(self.transfer.id)

    @transition
    def initiator_hangup(self):
        return self

    @transition
    def recipient_hangup(self):
        return self

    @transition
    def transferred_hangup(self):
        return self

    @classmethod
    def from_state(cls, *args, **kwargs):
        new_state = super(TransferStateEnded, cls).from_state(*args, **kwargs)
        new_state._notifier.ended(new_state.transfer)
        return new_state
