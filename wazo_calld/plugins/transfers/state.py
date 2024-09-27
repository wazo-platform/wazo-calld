# Copyright 2016-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, ClassVar

from ari.exceptions import ARINotFound
from wazo_amid_client import Client as AmidClient

from wazo_calld.ari_ import ARIClientProxy
from wazo_calld.plugin_helpers.ari_ import Channel
from wazo_calld.plugin_helpers.exceptions import BridgeNotFound

from . import ari_helpers
from .exceptions import (
    TransferAnswerError,
    TransferCancellationError,
    TransferCompletionError,
    TransferCreationError,
)
from .notifier import TransferNotifier
from .state_persistor import StatePersistor
from .transfer import InternalTransferStatus, Transfer, TransferStatus
from .transfer_lock import TransferLock

# avoid circular import
if TYPE_CHECKING:
    from .services import TransfersService

logger = logging.getLogger(__name__)
state_machine_lock = threading.RLock()
state_machine_locked = False  # RLock has no method .locked()


class StateFactory:
    '''
    Purpose: inject static dependencies in states
    '''

    def __init__(self, ari=None):
        self._state_constructors = {}
        self._ari = ari
        self._configured = False

    def set_dependencies(self, *dependencies):
        self._dependencies = dependencies
        self._configured = True

    def set_state_persistor(self, state_persistor):
        self._state_persistor = state_persistor

    @contextmanager
    def make(self, transfer_id):
        global state_machine_locked
        if not self._configured:
            raise RuntimeError('StateFactory is not configured')

        logger.debug(
            'Acquiring state machine lock from transfer %s',
            transfer_id,
        )
        state_machine_lock.acquire(timeout=10)
        state_machine_locked = True
        try:
            transfer = self._state_persistor.get(transfer_id)
            dependencies = list(self._dependencies) + [transfer]
            yield self._state_constructors[transfer.status](*dependencies)
        finally:
            logger.debug(
                'Releasing state machine lock from transfer %s',
                transfer_id,
            )
            state_machine_locked = False
            state_machine_lock.release()

    @contextmanager
    def make_from_class(self, state_class, transfer):
        global state_machine_locked
        if not self._configured:
            raise RuntimeError('StateFactory is not configured')
        dependencies = list(self._dependencies) + [transfer]
        transfer.status = state_class.name

        logger.debug(
            'Acquiring state machine lock from transfer %s for state %s',
            transfer.id,
            state_class.__name__,
        )
        state_machine_lock.acquire(timeout=10)
        state_machine_locked = True
        try:
            new_object = state_class(*dependencies)
            new_object.update_cache()  # ensure the transfer is stored in Asterisk vars cache
            yield new_object
        finally:
            logger.debug(
                'Releasing state machine lock from transfer %s for state %s',
                transfer.id,
                state_class.__name__,
            )
            state_machine_locked = False
            state_machine_lock.release()

    def state(self, wrapped_class):
        self._state_constructors[wrapped_class.name] = wrapped_class
        return wrapped_class


state_factory = StateFactory()


def transition(decorated):
    def decorator(state, *args, **kwargs):
        assert (
            state_machine_locked
        ), 'Transfer state machine was not locked before transition'
        logger.debug('transition start: %s -[%s]>', state.name, decorated.__name__)
        try:
            result = decorated(state, *args, **kwargs)
        except Exception:
            state._transfer_lock.release(state.transfer.initiator_call)
            raise

        logger.info(
            'Transition: %s -> %s -> %s',
            state.name,
            decorated.__name__,
            result.name,
        )
        result.update_cache()

        return result

    return decorator


class TransferState:
    name: ClassVar[InternalTransferStatus]

    def __init__(
        self,
        amid,
        ari,
        notifier,
        services,
        state_persistor,
        transfer_lock,
        transfer,
    ):
        self._amid: AmidClient = amid
        self._ari: ARIClientProxy = ari
        self._notifier: TransferNotifier = notifier
        self._services: TransfersService = services
        self._state_persistor: StatePersistor = state_persistor
        self._transfer_lock: TransferLock = transfer_lock
        self.transfer: Transfer = transfer

    @classmethod
    def from_state(cls, other_state):
        new_state = cls(
            other_state._amid,
            other_state._ari,
            other_state._notifier,
            other_state._services,
            other_state._state_persistor,
            other_state._transfer_lock,
            other_state.transfer,
        )
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
    def start(self):
        raise NotImplementedError(self.name)

    @transition
    def complete(self):
        raise NotImplementedError(self.name)

    @transition
    def cancel(self):
        raise NotImplementedError(self.name)

    @transition
    def transferred_moh_stop(self):
        return self

    def update_cache(self):
        raise NotImplementedError()

    def _hold_transferred_call(self):
        logger.debug(
            'putting transferred call %s on hold', self.transfer.transferred_call
        )
        try:
            ari_helpers.hold_transferred_call(
                self._ari, self._amid, self.transfer.transferred_call
            )
        except ARINotFound:
            pass

    def _unhold_transferred_call(self):
        logger.debug(
            'Removing transferred call %s from hold', self.transfer.transferred_call
        )
        ari_helpers.unhold_transferred_call(self._ari, self.transfer.transferred_call)

    def _move_transferred_call_to_transfer_bridge(self):
        logger.debug(
            'Moving transferred channel %s to transfer bridge',
            self.transfer.transferred_call,
        )
        bridge = self._get_or_create_transfer_bridge()
        bridge.addChannel(channel=self.transfer.transferred_call)
        logger.debug(
            'transferred call %s moved to bridge %s: %s',
            self.transfer.transferred_call,
            bridge.id,
        )

    def _move_recipient_call_to_transfer_bridge(self):
        assert (
            self.transfer.recipient_call
        ), f"No recipient_call for transfer {self.transfer.id}"
        logger.debug(
            'Moving recipient channel %s to transfer bridge',
            self.transfer.recipient_call,
        )
        bridge = self._get_or_create_transfer_bridge()
        bridge.addChannel(channel=self.transfer.recipient_call)
        logger.debug(
            'recipient channel %s moved to bridge %s: %s',
            self.transfer.recipient_call,
            bridge.id,
        )

    def _move_initiator_call_to_transfer_bridge(self):
        assert (
            self.transfer.initiator_call
        ), f"No initiator_call for transfer {self.transfer.id}"
        logger.debug(
            'Moving initiator channel %s to transfer bridge',
            self.transfer.initiator_call,
        )
        bridge = self._get_or_create_transfer_bridge()
        response = bridge.addChannel(channel=self.transfer.initiator_call)
        logger.debug(
            'initiator call %s moved to bridge %s: %s',
            self.transfer.initiator_call,
            bridge.id,
            response,
        )

    def _get_or_create_transfer_bridge(self):
        bridge_id = self.transfer.transfer_bridge_id
        try:
            bridge = self._ari.bridges.get(bridgeId=bridge_id)
        except ARINotFound:
            logger.debug('creating transfer bridge %s', bridge_id)
            bridge = self._ari.bridges.createWithId(
                type='mixing',
                name='transfer',
                bridgeId=bridge_id,
            )
            ari_helpers.set_bridge_variable(
                self._ari, bridge.id, 'WAZO_TRANSFER_ID', self.transfer.id
            )
        return bridge

    def _start_attended(self, context, exten, variables, timeout):
        # initiate attended transfer and notify

        self._hold_transferred_call()

        try:
            self._ari.channels.ring(channelId=self.transfer.initiator_call)
        except ARINotFound:
            logger.error('initiator hung up while creating transfer')

        try:
            self.transfer.recipient_call = self._services.originate_recipient(
                self.transfer.initiator_call,
                context,
                exten,
                self.transfer.id,
                variables,
                timeout,
            )
        except TransferCreationError as e:
            logger.error('%s %s', e.message, e.details)

        self._notifier.updated(self.transfer)

    def _set_initiator_variables(self):
        self._ari.channels.setChannelVar(
            channelId=self.transfer.initiator_call,
            variable='XIVO_TRANSFER_ROLE',
            value='initiator',
        )
        self._ari.channels.setChannelVar(
            channelId=self.transfer.initiator_call,
            variable='XIVO_TRANSFER_ID',
            value=self.transfer.id,
        )

    def _unset_initiator_variables(self):
        ari_helpers.unset_variable(
            self._ari, self._amid, self.transfer.initiator_call, 'XIVO_TRANSFER_ID'
        )
        ari_helpers.unset_variable(
            self._ari, self._amid, self.transfer.initiator_call, 'XIVO_TRANSFER_ROLE'
        )

    def _set_transferred_variables(self):
        self._ari.channels.setChannelVar(
            channelId=self.transfer.transferred_call,
            variable='XIVO_TRANSFER_ROLE',
            value='transferred',
        )
        self._ari.channels.setChannelVar(
            channelId=self.transfer.transferred_call,
            variable='XIVO_TRANSFER_ID',
            value=self.transfer.id,
        )

    def _unset_transferred_variables(self):
        ari_helpers.unset_variable(
            self._ari, self._amid, self.transfer.transferred_call, 'XIVO_TRANSFER_ID'
        )
        ari_helpers.unset_variable(
            self._ari, self._amid, self.transfer.transferred_call, 'XIVO_TRANSFER_ROLE'
        )

    def _set_recipient_variables(self):
        self._ari.channels.setChannelVar(
            channelId=self.transfer.recipient_call,
            variable='XIVO_TRANSFER_ROLE',
            value='recipient',
        )
        self._ari.channels.setChannelVar(
            channelId=self.transfer.recipient_call,
            variable='XIVO_TRANSFER_ID',
            value=self.transfer.id,
        )

    def _unset_recipient_variables(self):
        ari_helpers.unset_variable(
            self._ari, self._amid, self.transfer.recipient_call, 'XIVO_TRANSFER_ID'
        )
        ari_helpers.unset_variable(
            self._ari, self._amid, self.transfer.recipient_call, 'XIVO_TRANSFER_ROLE'
        )

    def _abandon(self):
        self._unset_recipient_variables()
        self._unset_initiator_variables()

        if self.transfer.transferred_call:
            try:
                self._ari.channels.hangup(channelId=self.transfer.transferred_call)
            except ARINotFound:
                pass

        self._notifier.abandoned(self.transfer)

    def _cancel(self):
        logger.debug('cancelling transfer %s', self.transfer.id)
        # cancel logic:
        # 1. unset transfer channel variables
        # 2. hangup transfer recipient channel
        # 3. stop ringing on initiator channel
        # 4. remove transferred party from hold
        # 5. bridge back transferred and initiator parties

        self._unset_transferred_variables()
        self._unset_initiator_variables()

        if self.transfer.recipient_call:
            try:
                self._ari.channels.hangup(channelId=self.transfer.recipient_call)
            except ARINotFound:
                pass

        try:
            ari_helpers.unring_initiator_call(self._ari, self.transfer.initiator_call)
        except ARINotFound:
            raise TransferCancellationError(self.transfer.id, 'initiator hung up')

        try:
            self._unhold_transferred_call()
            self._move_transferred_call_to_transfer_bridge()
        except ARINotFound:
            raise TransferCancellationError(
                self.transfer.id, 'transferred party hung up'
            )

        try:
            self._move_initiator_call_to_transfer_bridge()
        except ARINotFound:
            raise TransferCancellationError(self.transfer.id, 'initiator hung up')

        self._notifier.cancelled(self.transfer)


@state_factory.state
class TransferStateReady(TransferState):
    name = TransferStatus.ready

    @transition
    def start(
        self,
        context,
        exten,
        variables,
        timeout,
    ):
        initiator_channel = Channel(self.transfer.initiator_call, self._ari)
        transferred_channel = Channel(self.transfer.transferred_call, self._ari)
        initiator_uuid = initiator_channel.user()
        if initiator_uuid is None:
            raise TransferCreationError('initiator has no user UUID')

        try:
            self._set_transferred_variables()
            self._set_initiator_variables()
        except ARINotFound:
            raise TransferCreationError('some channel got hung up')

        # destroy existing transferred-initiator bridge
        try:
            bridge = initiator_channel.bridge()
        except BridgeNotFound:
            pass
        else:
            if bridge.has_only_channel_ids(
                transferred_channel.id, initiator_channel.id
            ):
                # Deleting the bridge prevents the bridge auto-cleaner stasis handler to
                # hangup one of the channels before they get transferred
                self._ari.bridges.destroy(bridgeId=bridge.id)

        self._start_attended(context, exten, variables, timeout)

        return TransferStateRingback.from_state(self)

    def update_cache(self):
        self._state_persistor.upsert(self.transfer)


@state_factory.state
class TransferStateNonStasis(TransferState):
    name = 'non_stasis'

    @transition
    def start(
        self,
        context,
        exten,
        variables,
        timeout,
    ):
        try:
            ari_helpers.convert_transfer_to_stasis(
                self._ari,
                self._amid,
                self.transfer.transferred_call,
                self.transfer.initiator_call,
                context,
                exten,
                self.transfer.id,
                variables,
                timeout,
            )
        except ARINotFound:
            raise TransferCreationError('channel not found')

        return TransferStateMovingToStasisNoneReady.from_state(self)

    def update_cache(self):
        self._state_persistor.upsert(self.transfer)


@state_factory.state
class TransferStateMovingToStasisNoneReady(TransferState):
    name = 'none_moved_to_stasis'

    @transition
    def complete(self):
        self.transfer.flow = 'blind'

        return self

    @transition
    def initiator_hangup(self):
        self.transfer.flow = 'blind'

        return self

    @transition
    def initiator_joined_stasis(self):
        return TransferStateMovingToStasisInitiatorReady.from_state(self)

    @transition
    def transferred_hangup(self):
        self._abandon()
        return TransferStateEnded.from_state(self)

    @transition
    def transferred_joined_stasis(self):

        return TransferStateMovingToStasisTransferredReady.from_state(self)

    def transferred_moh_stop(self):
        logger.warning('MOH stopped playing while starting transfer. Playing silence.')
        try:
            self._ari.channels.startSilence(channelId=self.transfer.transferred_call)
        except ARINotFound:
            pass

        return self

    def update_cache(self):
        self._state_persistor.upsert(self.transfer)


@state_factory.state
class TransferStateMovingToStasisInitiatorReady(TransferState):
    name = 'initiator_moved_to_stasis'

    @transition
    def complete(self):
        self.transfer.flow = 'blind'

        return self

    @transition
    def initiator_hangup(self):
        self.transfer.flow = 'blind'

        return self

    @transition
    def transferred_joined_stasis(self):
        # TODO: any error to interpret?
        context, exten, variables, timeout = ari_helpers.get_initial_transfer_variables(
            self._ari, self.transfer.initiator_call
        )

        self._start_attended(context, exten, variables, timeout)
        return TransferStateRingback.from_state(self)

    @transition
    def transferred_hangup(self):
        self._abandon()
        return TransferStateEnded.from_state(self)

    def update_cache(self):
        self._state_persistor.upsert(self.transfer)


@state_factory.state
class TransferStateMovingToStasisTransferredReady(TransferState):
    name = 'transferred_moved_to_stasis'

    @transition
    def initiator_hangup(self):
        self.transfer.flow = 'blind'

        return self

    @transition
    def initiator_joined_stasis(self):
        # TODO: any error to interpret?
        context, exten, variables, timeout = ari_helpers.get_initial_transfer_variables(
            self._ari, self.transfer.initiator_call
        )

        self._start_attended(context, exten, variables, timeout)
        return TransferStateRingback.from_state(self)

    @transition
    def transferred_hangup(self):
        self._abandon()
        return TransferStateEnded.from_state(self)

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
            self._unhold_transferred_call()
        except ARINotFound:
            raise TransferCompletionError(self.transfer.id, 'transferred party hung up')

        try:
            self._ari.channels.ring(channelId=self.transfer.transferred_call)
        except ARINotFound:
            raise TransferCompletionError(self.transfer.id, 'transferred party hung up')

        self.transfer.flow = 'blind'
        self._notifier.completed(self.transfer)

        return TransferStateBlindTransferred.from_state(self)

    @transition
    def recipient_hangup(self):
        self._cancel()
        return TransferStateEnded.from_state(self)

    @transition
    def complete(self):
        self._unhold_transferred_call()
        self._move_transferred_call_to_transfer_bridge()

        try:
            self._ari.channels.hangup(channelId=self.transfer.initiator_call)
        except ARINotFound:
            pass

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

        self._move_initiator_call_to_transfer_bridge()
        self._move_recipient_call_to_transfer_bridge()

        return TransferStateAnswered.from_state(self)

    def transferred_moh_stop(self):
        logger.warning(
            'MOH stopped playing while transfer was ringing. Playing silence.'
        )
        try:
            self._ari.channels.startSilence(channelId=self.transfer.transferred_call)
        except ARINotFound:
            pass
        return self

    def update_cache(self):
        self._state_persistor.upsert(self.transfer)


@state_factory.state
class TransferStateBlindTransferred(TransferState):
    name = TransferStatus.blind_transferred

    @transition
    def transferred_hangup(self):
        self._abandon()
        if self.transfer.recipient_call:
            try:
                self._ari.channels.hangup(channelId=self.transfer.recipient_call)
            except ARINotFound:
                pass

        return TransferStateEnded.from_state(self)

    @transition
    def initiator_hangup(self):
        return self

    @transition
    def recipient_hangup(self):
        self._abandon()
        return TransferStateEnded.from_state(self)

    @transition
    def recipient_answer(self):
        self._unset_transferred_variables()
        self._unset_recipient_variables()

        try:
            ari_helpers.unring_initiator_call(self._ari, self.transfer.transferred_call)
        except ARINotFound:
            raise TransferAnswerError(self.transfer.id, 'transferred hung up')

        self._move_transferred_call_to_transfer_bridge()
        self._move_recipient_call_to_transfer_bridge()

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
        # same as complete transition, but initiator already hung up
        self._unhold_transferred_call()
        self._move_transferred_call_to_transfer_bridge()

        self._unset_transferred_variables()
        self._unset_recipient_variables()

        self._notifier.completed(self.transfer)

        return TransferStateEnded.from_state(self)

    @transition
    def recipient_hangup(self):
        self._cancel()
        return TransferStateEnded.from_state(self)

    @transition
    def complete(self):
        # NOTE(clanglois): transferred channel must be moved into transfer bridge
        # before initiator hangup, otherwise transfer bridge may be destroyed
        self._unhold_transferred_call()
        self._move_transferred_call_to_transfer_bridge()

        self._unset_transferred_variables()
        self._unset_recipient_variables()

        try:
            self._ari.channels.hangup(channelId=self.transfer.initiator_call)
        except ARINotFound:
            pass

        self._notifier.completed(self.transfer)

        return TransferStateEnded.from_state(self)

    @transition
    def cancel(self):
        self._cancel()
        return TransferStateEnded.from_state(self)

    def transferred_moh_stop(self):
        logger.warning(
            'MOH stopped playing while transfer was answered. Playing silence.'
        )
        try:
            self._ari.channels.startSilence(channelId=self.transfer.transferred_call)
        except ARINotFound:
            pass

        return self

    def update_cache(self):
        self._state_persistor.upsert(self.transfer)

    @classmethod
    def from_state(cls, *args, **kwargs):
        new_state = super().from_state(*args, **kwargs)
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
        new_state = super().from_state(*args, **kwargs)
        new_state._notifier.ended(new_state.transfer)
        new_state._transfer_lock.release(new_state.transfer.initiator_call)
        return new_state
