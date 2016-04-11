# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from contextlib import contextmanager
from requests import HTTPError
from xivo_amid_client import Client as AmidClient
from xivo_ctid_ng.core.ari_ import APPLICATION_NAME
from xivo_ctid_ng.core.ari_ import not_found
from xivo_ctid_ng.core.ari_ import not_in_stasis

from .exceptions import NoSuchTransfer
from .exceptions import TransferError
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
            import uuid
            transfer_id = str(uuid.uuid4())
            self.convert_transfer_to_stasis(transferred_call, initiator_call, context, exten, transfer_id)
            transfer = Transfer(transfer_id)
            transfer.initiator_call = initiator_call
            transfer.transferred_call = transferred_call
            transfer.status = TransferStatus.starting
        else:
            transfer_bridge = self.ari.bridges.create(type='mixing', name='transfer')
            transfer_id = transfer_bridge.id
            self.ari.channels.setChannelVar(channelId=transferred_call, variable='XIVO_TRANSFER_ROLE', value='transferred')
            self.ari.channels.setChannelVar(channelId=initiator_call, variable='XIVO_TRANSFER_ROLE', value='initiator')
            transfer_bridge.addChannel(channel=transferred_call)
            transfer_bridge.addChannel(channel=initiator_call)

            self.hold_transferred_call(transferred_call)
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
        except HTTPError as e:
            if not_found(e):
                raise TransferError('{call}: no app_instance found'.format(call=initiator_call))
            raise
        recipient_endpoint = 'Local/{exten}@{context}'.format(exten=exten, context=context)
        app_args = [app_instance, 'transfer_recipient_called', transfer_id]
        originate_variables = {'XIVO_TRANSFER_ROLE': 'recipient',
                               'XIVO_TRANSFER_ID': transfer_id}
        recipient_call = self.ari.channels.originate(endpoint=recipient_endpoint,
                                                     app=APPLICATION_NAME,
                                                     appArgs=app_args,
                                                     variables={'variables': originate_variables})
        return recipient_call.id

    def get(self, transfer_id):
        try:
            self.state_persistor.get(transfer_id)
        except KeyError:
            raise NoSuchTransfer(transfer_id)

        try:
            bridge = self.ari.bridges.get(bridgeId=transfer_id)
        except HTTPError as e:
            if not_found(e):
                raise NoSuchTransfer(transfer_id)
            raise
        transfer = Transfer(transfer_id)
        channels = [self.ari.channels.get(channelId=channel_id) for channel_id in bridge.json['channels']]
        for channel in channels:
            value = channel.getChannelVar(variable='XIVO_TRANSFER_ROLE')['value']
            if value == 'transferred':
                transfer.transferred_call = channel.id
            elif value == 'initiator':
                transfer.initiator_call = channel.id
            elif value == 'recipient':
                transfer.recipient_call = channel.id
                if channel.json['state'] == 'Ringing':
                    transfer.status = TransferStatus.ringback
                else:
                    transfer.status = TransferStatus.answered

        if not transfer.recipient_call:
            channel_transferid_role = []
            for channel in self.ari.channels.list():
                try:
                    transfer_id = channel.getChannelVar(variable='XIVO_TRANSFER_ID')['value']
                except HTTPError as e:
                    if not_found(e):
                        transfer_id = None
                    else:
                        raise
                try:
                    transfer_role = channel.getChannelVar(variable='XIVO_TRANSFER_ROLE')['value']
                except HTTPError as e:
                    if not_found(e):
                        transfer_role = None
                    else:
                        raise
                channel_transferid_role.append((channel.id, transfer_id, transfer_role))

            try:
                transfer.recipient_call = next(channel_id for channel_id, transfer_id, transfer_role in channel_transferid_role
                                               if transfer_id == transfer.id and transfer_role == 'recipient')
            except StopIteration:
                transfer.recipient_call = None

        # TODO: transfer is invalid if NOT 3 channels or NOT transferred + initiator + recipient
        return transfer

    def complete(self, transfer_id):
        transfer = self.get(transfer_id)

        if transfer.initiator_call:
            self.ari.channels.hangup(channelId=transfer.initiator_call)
        self.unhold_transferred_call(transfer.transferred_call)

        self.ari.channels.setChannelVar(channelId=transfer.transferred_call, variable='XIVO_TRANSFER_ID', value='')
        self.ari.channels.setChannelVar(channelId=transfer.transferred_call, variable='XIVO_TRANSFER_ROLE', value='')
        self.ari.channels.setChannelVar(channelId=transfer.recipient_call, variable='XIVO_TRANSFER_ID', value='')
        self.ari.channels.setChannelVar(channelId=transfer.recipient_call, variable='XIVO_TRANSFER_ROLE', value='')
        self.state_persistor.remove(transfer_id)

    def cancel(self, transfer_id):
        transfer = self.get(transfer_id)

        if transfer.recipient_call:
            self.ari.channels.hangup(channelId=transfer.recipient_call)
        self.unhold_transferred_call(transfer.transferred_call)

        self.ari.channels.setChannelVar(channelId=transfer.transferred_call, variable='XIVO_TRANSFER_ID', value='')
        self.ari.channels.setChannelVar(channelId=transfer.transferred_call, variable='XIVO_TRANSFER_ROLE', value='')
        self.ari.channels.setChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_ID', value='')
        self.ari.channels.setChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_ROLE', value='')
        self.state_persistor.remove(transfer_id)

    def abandon(self, transfer_id):
        transfer = self.get(transfer_id)

        if transfer.transferred_call:
            self.ari.channels.hangup(channelId=transfer.transferred_call)

        self.ari.channels.setChannelVar(channelId=transfer.recipient_call, variable='XIVO_TRANSFER_ID', value='')
        self.ari.channels.setChannelVar(channelId=transfer.recipient_call, variable='XIVO_TRANSFER_ROLE', value='')
        self.ari.channels.setChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_ID', value='')
        self.ari.channels.setChannelVar(channelId=transfer.initiator_call, variable='XIVO_TRANSFER_ROLE', value='')
        self.state_persistor.remove(transfer_id)

    def is_in_stasis(self, call_id):
        try:
            self.ari.channels.setChannelVar(channelId=call_id, variable='XIVO_TEST_STASIS')
            return True
        except HTTPError as e:
            if not_in_stasis(e):
                return False
            raise

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
