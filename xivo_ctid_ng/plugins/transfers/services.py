# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
import uuid

from contextlib import contextmanager
from requests import HTTPError
from xivo_amid_client import Client as AmidClient
from xivo_ctid_ng.core.ari_ import APPLICATION_NAME
from xivo_ctid_ng.core.ari_ import not_found
from xivo_ctid_ng.core.ari_ import not_in_stasis
from xivo_ctid_ng.core.exceptions import ARINotFound
from xivo_ctid_ng.core.exceptions import ARINotInStasis

from .exceptions import NoSuchTransfer
from .exceptions import TransferCreationError
from .exceptions import TransferCancellationError
from .exceptions import TransferCompletionError
from .transfer import Transfer, TransferStatus

logger = logging.getLogger(__name__)


@contextmanager
def new_amid_client(config):
    yield AmidClient(**config)


class TransfersService(object):
    def __init__(self, ari, amid_config, state_persistor):
        self.ari = ari
        self.amid_config = amid_config
        self.state_persistor = state_persistor

    def set_token(self, auth_token):
        self.auth_token = auth_token

    def create(self,
               transferred_call,
               initiator_call,
               context,
               exten):

        if not (self.is_in_stasis(transferred_call) and self.is_in_stasis(initiator_call)):
            transfer_id = str(uuid.uuid4())
            self.convert_transfer_to_stasis(transferred_call, initiator_call, context, exten, transfer_id)
            transfer = Transfer(transfer_id)
            transfer.initiator_call = initiator_call
            transfer.transferred_call = transferred_call
            transfer.status = TransferStatus.starting
        else:
            transfer_bridge = self.ari.bridges.create(type='mixing', name='transfer')
            transfer_id = transfer_bridge.id
            try:
                self.ari.channels.setChannelVar(channelId=transferred_call, variable='XIVO_TRANSFER_ROLE', value='transferred')
                self.ari.channels.setChannelVar(channelId=transferred_call, variable='XIVO_TRANSFER_ID', value=transfer_id)
                self.ari.channels.setChannelVar(channelId=initiator_call, variable='XIVO_TRANSFER_ROLE', value='initiator')
                self.ari.channels.setChannelVar(channelId=initiator_call, variable='XIVO_TRANSFER_ID', value=transfer_id)
                transfer_bridge.addChannel(channel=transferred_call)
                transfer_bridge.addChannel(channel=initiator_call)
            except ARINotFound:
                raise TransferCreationError('some channel got hung up')

            try:
                self.hold_transferred_call(transferred_call)
            except ARINotFound:
                raise TransferCreationError('transferred call hung up')

            recipient_call = self.originate_recipient(initiator_call, context, exten, transfer_id)

            transfer = Transfer(transfer_id)
            transfer.transferred_call = transferred_call
            transfer.initiator_call = initiator_call
            transfer.recipient_call = recipient_call
            transfer.status = TransferStatus.ringback

        self.state_persistor.upsert(transfer)
        return transfer

    def hold_transferred_call(self, transferred_call):
        self.ari.channels.mute(channelId=transferred_call, direction='in')
        self.ari.channels.hold(channelId=transferred_call)
        self.ari.channels.startMoh(channelId=transferred_call)

    def unhold_transferred_call(self, transferred_call):
        self.ari.channels.unmute(channelId=transferred_call, direction='in')
        self.ari.channels.unhold(channelId=transferred_call)
        self.ari.channels.stopMoh(channelId=transferred_call)

    def originate_recipient(self, initiator_call, context, exten, transfer_id):
        try:
            app_instance = self.ari.channels.getChannelVar(channelId=initiator_call, variable='XIVO_STASIS_ARGS')['value']
        except ARINotFound:
            raise TransferCreationError('{call}: no app_instance found'.format(call=initiator_call))
        recipient_endpoint = 'Local/{exten}@{context}'.format(exten=exten, context=context)
        app_args = [app_instance, 'transfer_recipient_called', transfer_id]
        originate_variables = {'XIVO_TRANSFER_ROLE': 'recipient',
                               'XIVO_TRANSFER_ID': transfer_id,
                               'XIVO_HANGUP_LOCK_TARGET': initiator_call}
        new_channel = self.ari.channels.originate(endpoint=recipient_endpoint,
                                                  app=APPLICATION_NAME,
                                                  appArgs=app_args,
                                                  variables={'variables': originate_variables})
        recipient_call = new_channel.id
        try:
            self.ari.channels.setChannelVar(channelId=initiator_call, variable='XIVO_HANGUP_LOCK_SOURCE', value=recipient_call)
        except ARINotFound:
            raise TransferCreationError('initiator hung up')
        return recipient_call

    def get(self, transfer_id):
        try:
            return self.state_persistor.get(transfer_id)
        except KeyError:
            raise NoSuchTransfer(transfer_id)

    def complete(self, transfer_id):
        transfer = self.get(transfer_id)

        try:
            self.ari.channels.setChannelVar(channelId=transfer.transferred_call, variable='XIVO_TRANSFER_ID', value='')
            self.ari.channels.setChannelVar(channelId=transfer.transferred_call, variable='XIVO_TRANSFER_ROLE', value='')
        except ARINotFound:
            pass

        try:
            self.ari.channels.setChannelVar(channelId=transfer.recipient_call, variable='XIVO_TRANSFER_ID', value='')
            self.ari.channels.setChannelVar(channelId=transfer.recipient_call, variable='XIVO_TRANSFER_ROLE', value='')
        except ARINotInStasis:
            pass
        except ARINotFound:
            raise TransferCompletionError(transfer_id, 'transfer recipient hung up')

        self.state_persistor.remove(transfer_id)
        if transfer.initiator_call:
            try:
                self.ari.channels.hangup(channelId=transfer.initiator_call)
            except ARINotFound:
                pass
        try:
            self.unhold_transferred_call(transfer.transferred_call)
        except ARINotFound:
            raise TransferCompletionError(transfer_id, 'transferred hung up')

    def cancel(self, transfer_id):
        transfer = self.get(transfer_id)

        try:
            self.ari.channels.setChannelVar(channelId=transfer.transferred_call, variable='XIVO_TRANSFER_ID', value='')
            self.ari.channels.setChannelVar(channelId=transfer.transferred_call, variable='XIVO_TRANSFER_ROLE', value='')
        except ARINotFound:
            pass

        try:
            self.ari.channels.setChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_ID', value='')
            self.ari.channels.setChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_ROLE', value='')
        except ARINotFound:
            raise TransferCancellationError(transfer_id, 'initiator hung up')

        self.state_persistor.remove(transfer_id)
        if transfer.recipient_call:
            try:
                self.ari.channels.hangup(channelId=transfer.recipient_call)
            except ARINotFound:
                pass

        try:
            self.unhold_transferred_call(transfer.transferred_call)
        except ARINotFound:
            raise TransferCancellationError(transfer_id, 'transferred hung up')

    def abandon(self, transfer_id):
        transfer = self.get(transfer_id)

        try:
            self.ari.channels.setChannelVar(channelId=transfer.recipient_call, variable='XIVO_TRANSFER_ID', value='')
            self.ari.channels.setChannelVar(channelId=transfer.recipient_call, variable='XIVO_TRANSFER_ROLE', value='')
        except (ARINotFound, ARINotInStasis):
            pass
        try:
            self.ari.channels.setChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_ID', value='')
            self.ari.channels.setChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_ROLE', value='')
        except ARINotFound:
            pass

        self.state_persistor.remove(transfer_id)
        if transfer.transferred_call:
            try:
                self.ari.channels.hangup(channelId=transfer.transferred_call)
            except ARINotFound:
                pass

    def is_in_stasis(self, call_id):
        try:
            self.ari.channels.setChannelVar(channelId=call_id, variable='XIVO_TEST_STASIS')
            return True
        except ARINotInStasis:
            return False

    def convert_transfer_to_stasis(self, transferred_call, initiator_call, context, exten, transfer_id):
        set_variables = [(transferred_call, 'XIVO_TRANSFER_ROLE', 'transferred'),
                         (transferred_call, 'XIVO_TRANSFER_ID', transfer_id),
                         (transferred_call, 'XIVO_TRANSFER_DESTINATION_CONTEXT', context),
                         (transferred_call, 'XIVO_TRANSFER_DESTINATION_EXTEN', exten),
                         (initiator_call, 'XIVO_TRANSFER_ROLE', 'initiator'),
                         (initiator_call, 'XIVO_TRANSFER_ID', transfer_id),
                         (initiator_call, 'XIVO_TRANSFER_DESTINATION_CONTEXT', context),
                         (initiator_call, 'XIVO_TRANSFER_DESTINATION_EXTEN', exten)]
        with new_amid_client(self.amid_config) as ami:
            for channel_id, variable, value in set_variables:
                parameters = {'Channel': channel_id,
                              'Variable': variable,
                              'Value': value}
                ami.action('Setvar', parameters, token=self.auth_token)

            destination = {'Channel': transferred_call,
                           'ExtraChannel': initiator_call,
                           'Context': 'convert_to_stasis',
                           'Exten': 'transfer',
                           'Priority': 1}
            ami.action('Redirect', destination, token=self.auth_token)
