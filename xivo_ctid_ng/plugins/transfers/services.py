# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
from ari.exceptions import ARINotFound
from xivo.caller_id import assemble_caller_id

from xivo_ctid_ng.core.ari_ import APPLICATION_NAME
from xivo_ctid_ng.core.ari_helpers import Channel
from xivo_ctid_ng.core.confd_helpers import User
from xivo_ctid_ng.core.exceptions import NotEnoughChannels
from xivo_ctid_ng.core.exceptions import TooManyChannels
from xivo_ctid_ng.plugins.calls.state_persistor import ReadOnlyStatePersistor as ReadOnlyCallStates

from xivo_ctid_ng.core import ami_helpers
from . import ari_helpers
from .exceptions import InvalidExtension
from .exceptions import NoSuchTransfer
from .exceptions import TransferCreationError
from .exceptions import TooManyTransferredCandidates
from .state import TransferStateReadyNonStasis, TransferStateReady

logger = logging.getLogger(__name__)


class TransfersService(object):
    def __init__(self, amid_client, ari, confd_client, state_factory, state_persistor):
        self.amid_client = amid_client
        self.ari = ari
        self.confd_client = confd_client
        self.state_persistor = state_persistor
        self.state_factory = state_factory
        self.call_states = ReadOnlyCallStates(self.ari)

    def create(self, transferred_call, initiator_call, context, exten, flow, variables):
        try:
            transferred_channel = self.ari.channels.get(channelId=transferred_call)
            initiator_channel = self.ari.channels.get(channelId=initiator_call)
        except ARINotFound:
            raise TransferCreationError('channel not found')

        if not ami_helpers.extension_exists(self.amid_client, context, exten):
            raise InvalidExtension(context, exten)

        if not (ari_helpers.is_in_stasis(self.ari, transferred_call) and
                ari_helpers.is_in_stasis(self.ari, initiator_call)):
            transfer_state = self.state_factory.make_from_class(TransferStateReadyNonStasis)
        else:
            transfer_state = self.state_factory.make_from_class(TransferStateReady)

        new_state = transfer_state.create(transferred_channel, initiator_channel, context, exten, variables)
        if flow == 'blind':
            new_state = new_state.complete()

        return new_state.transfer

    def create_from_user(self, initiator_call, exten, flow, user_uuid):
        if not ari_helpers.channel_exists(self.ari, initiator_call):
            raise TransferCreationError('initiator channel not found')

        if Channel(initiator_call, self.ari).user() != user_uuid:
            raise TransferCreationError('initiator call does not belong to authenticated user')

        try:
            transferred_call = Channel(initiator_call, self.ari).only_connected_channel()
        except TooManyChannels as e:
            raise TooManyTransferredCandidates(e.channels)
        except NotEnoughChannels as e:
            raise TransferCreationError('transferred channel not found')

        context = User(user_uuid, self.confd_client).main_line().context()

        return self.create(transferred_call, initiator_call, context, exten, flow, variables={})

    def originate_recipient(self, initiator_call, context, exten, transfer_id, variables):
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
        new_channel = self.ari.channels.originate(endpoint=recipient_endpoint,
                                                  app=APPLICATION_NAME,
                                                  appArgs=app_args,
                                                  callerId=caller_id,
                                                  variables={'variables': originate_variables})
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

    def cancel(self, transfer_id):
        transfer = self.get(transfer_id)
        transfer_state = self.state_factory.make(transfer)
        transfer_state.cancel()
