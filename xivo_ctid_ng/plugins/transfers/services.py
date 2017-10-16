# -*- coding: utf-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
from ari.exceptions import ARINotFound
from xivo.caller_id import assemble_caller_id

from xivo_ctid_ng.ari_ import APPLICATION_NAME
from xivo_ctid_ng.exceptions import UserPermissionDenied
from xivo_ctid_ng.exceptions import InvalidExtension
from xivo_ctid_ng.helpers.ari_ import Channel
from xivo_ctid_ng.helpers.confd import User
from xivo_ctid_ng.helpers.exceptions import NotEnoughChannels
from xivo_ctid_ng.helpers.exceptions import TooManyChannels
from xivo_ctid_ng.plugins.calls.state_persistor import ReadOnlyStatePersistor as ReadOnlyCallStates

from xivo_ctid_ng.helpers import ami
from . import ari_helpers
from .exceptions import NoSuchTransfer
from .exceptions import TooManyTransferredCandidates
from .exceptions import TransferAlreadyStarted
from .exceptions import TransferCreationError
from .state import TransferStateReadyNonStasis, TransferStateReady

logger = logging.getLogger(__name__)


class TransfersService(object):
    def __init__(self, amid_client, ari, confd_client, state_factory, state_persistor, transfer_lock):
        self.amid_client = amid_client
        self.ari = ari
        self.confd_client = confd_client
        self.state_persistor = state_persistor
        self.state_factory = state_factory
        self.call_states = ReadOnlyCallStates(self.ari)
        self.transfer_lock = transfer_lock

    def list_from_user(self, user_uuid):
        transfers = self.state_persistor.list()
        return [transfer for transfer in transfers if transfer.initiator_uuid == user_uuid]

    def create(self, transferred_call, initiator_call, context, exten, flow, variables, timeout):
        try:
            transferred_channel = self.ari.channels.get(channelId=transferred_call)
            initiator_channel = self.ari.channels.get(channelId=initiator_call)
        except ARINotFound:
            raise TransferCreationError('channel not found')

        if not ami.extension_exists(self.amid_client, context, exten):
            raise InvalidExtension(context, exten)

        if not self.transfer_lock.acquire(initiator_call):
            raise TransferAlreadyStarted(initiator_call)

        if not (Channel(transferred_call, self.ari).is_in_stasis() and
                Channel(initiator_call, self.ari).is_in_stasis()):
            transfer_state = self.state_factory.make_from_class(TransferStateReadyNonStasis)
        else:
            transfer_state = self.state_factory.make_from_class(TransferStateReady)

        try:
            new_state = transfer_state.create(transferred_channel, initiator_channel, context, exten, variables, timeout)
        except Exception:
            self.transfer_lock.release(initiator_call)
            raise
        if flow == 'blind':
            new_state = new_state.complete()

        return new_state.transfer

    def create_from_user(self, initiator_call, exten, flow, timeout, user_uuid):
        if not Channel(initiator_call, self.ari).exists():
            raise TransferCreationError('initiator channel not found')

        if Channel(initiator_call, self.ari).user() != user_uuid:
            raise UserPermissionDenied(user_uuid, {'call': initiator_call})

        try:
            transferred_call = Channel(initiator_call, self.ari).only_connected_channel().id
        except TooManyChannels as e:
            raise TooManyTransferredCandidates(e.channels)
        except NotEnoughChannels as e:
            raise TransferCreationError('transferred channel not found')

        context = User(user_uuid, self.confd_client).main_line().context()

        return self.create(transferred_call, initiator_call, context, exten, flow, variables={}, timeout=timeout)

    def originate_recipient(self, initiator_call, context, exten, transfer_id, variables, timeout):
        try:
            app_instance = self.call_states.get(initiator_call).app_instance
        except KeyError:
            raise TransferCreationError('{call}: no app_instance found'.format(call=initiator_call))
        initiator_channel = self.ari.channels.get(channelId=initiator_call)
        caller_id = assemble_caller_id(initiator_channel.json['caller']['name'], initiator_channel.json['caller']['number']).encode('utf-8')
        recipient_endpoint = 'Local/{exten}@{context}'.format(exten=exten, context=context)
        app_args = [app_instance, 'transfer_recipient_called', transfer_id]
        originate_variables = dict(variables)
        originate_variables['XIVO_TRANSFER_ROLE'] = 'recipient'
        originate_variables['XIVO_TRANSFER_ID'] = transfer_id
        originate_variables['CHANNEL(language)'] = initiator_channel.getChannelVar(variable='CHANNEL(language)')['value']
        try:
            originate_variables['XIVO_USERID'] = initiator_channel.getChannelVar(variable='XIVO_USERID')['value']
        except ARINotFound:
            pass
        try:
            originate_variables['XIVO_USERUUID'] = initiator_channel.getChannelVar(variable='XIVO_USERUUID')['value']
        except ARINotFound:
            pass
        timeout = -1 if timeout is None else timeout

        new_channel = self.ari.channels.originate(endpoint=recipient_endpoint,
                                                  app=APPLICATION_NAME,
                                                  appArgs=app_args,
                                                  callerId=caller_id,
                                                  variables={'variables': originate_variables},
                                                  timeout=timeout,
                                                  originator=initiator_call)
        recipient_call = new_channel.id

        try:
            ari_helpers.set_bridge_variable(self.ari, transfer_id, 'XIVO_HANGUP_LOCK_SOURCE', recipient_call)
        except ARINotFound:
            raise TransferCreationError('bridge not found')

        return recipient_call

    def get(self, transfer_id):
        try:
            return self.state_persistor.get(transfer_id)
        except KeyError:
            raise NoSuchTransfer(transfer_id)

    def complete(self, transfer_id):
        transfer = self.get(transfer_id)

        transfer_state = self.state_factory.make(transfer)
        transfer_state.complete()

    def complete_from_user(self, transfer_id, user_uuid):
        transfer = self.get(transfer_id)
        if transfer.initiator_uuid != user_uuid:
            raise UserPermissionDenied(user_uuid, {'transfer': transfer_id})

        transfer_state = self.state_factory.make(transfer)
        transfer_state.complete()

    def cancel(self, transfer_id):
        transfer = self.get(transfer_id)
        transfer_state = self.state_factory.make(transfer)
        transfer_state.cancel()

    def cancel_from_user(self, transfer_id, user_uuid):
        transfer = self.get(transfer_id)
        if transfer.initiator_uuid != user_uuid:
            raise UserPermissionDenied(user_uuid, {'transfer': transfer_id})

        transfer_state = self.state_factory.make(transfer)
        transfer_state.cancel()
