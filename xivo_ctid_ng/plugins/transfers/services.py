# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
import requests

from xivo_ctid_ng.core.ari_ import APPLICATION_NAME
from xivo_ctid_ng.core.ari_ import not_found

from .exceptions import NoSuchTransfer
from .exceptions import TransferError
from .transfer import Transfer

logger = logging.getLogger(__name__)


class TransfersService(object):
    def __init__(self, ari):
        self.ari = ari

    def create(self,
               transferred_call,
               initiator_call,
               context,
               exten):

        self.ari.channels.setChannelVar(channelId=transferred_call, variable='XIVO_TRANSFER', value='transferred')
        self.ari.channels.setChannelVar(channelId=initiator_call, variable='XIVO_TRANSFER', value='initiator')

        transfer_bridge = self.ari.bridges.create(type='mixing', name='transfer')
        transfer_bridge.addChannel(channel=transferred_call)

        self.ari.channels.mute(channelId=transferred_call, direction='in')
        self.ari.channels.hold(channelId=transferred_call)
        self.ari.channels.startMoh(channelId=transferred_call)

        transfer_bridge.addChannel(channel=initiator_call)

        try:
            app_instance = self.ari.channels.getChannelVar(channelId=initiator_call, variable='XIVO_STASIS_ARGS')['value']
        except requests.HTTPError as e:
            if not_found(e):
                raise TransferError('{call}: no app_instance found'.format(call=initiator_call))
            raise
        recipient_endpoint = 'Local/{exten}@{context}'.format(exten=exten, context=context)
        app_args = [app_instance, 'transfer_recipient_called', transfer_bridge.id]
        recipient_channel = self.ari.channels.originate(endpoint=recipient_endpoint,
                                                        app=APPLICATION_NAME,
                                                        appArgs=app_args,
                                                        variables={'variables': {'XIVO_TRANSFER': 'recipient'}})
        transfer = Transfer(transfer_bridge.id)
        transfer.transferred_call = transferred_call
        transfer.initiator_call = initiator_call
        transfer.recipient_call = recipient_channel.id
        return transfer

    def get(self, transfer_id):
        bridges = self.ari.bridges.list()
        try:
            bridge = next(bridge for bridge in bridges
                          if bridge.json['name'] == 'transfer' and bridge.id == transfer_id)
        except StopIteration:
            raise NoSuchTransfer(transfer_id)
        transfer = Transfer(transfer_id)
        channels = [self.ari.channels.get(channelId=channel_id) for channel_id in bridge.json['channels']]
        for channel in channels:
            value = self.ari.channels.getChannelVar(channelId=channel.id, variable='XIVO_TRANSFER')['value']
            if value == 'transferred':
                transfer.transferred_call = channel.id
            elif value == 'initiator':
                transfer.initiator_call = channel.id
            elif value == 'recipient':
                transfer.recipient_call = channel.id
                if channel.json['state'] == 'Ringing':
                    transfer.status = 'ringback'
                else:
                    transfer.status = 'answered'
        # TODO: transfer is invalid if NOT 3 channels or NOT transferred + initiator + recipient
        return transfer

    def complete(self, transfer_id):
        transfer = self.get(transfer_id)

        self.ari.channels.hangup(channelId=transfer.initiator_call)

        self.ari.channels.unmute(channelId=transfer.transferred_call, direction='in')
        self.ari.channels.unhold(channelId=transfer.transferred_call)
        self.ari.channels.stopMoh(channelId=transfer.transferred_call)

        self.ari.channels.setChannelVar(channelId=transfer.transferred_call, variable='XIVO_TRANSFER', value='')
        self.ari.channels.setChannelVar(channelId=transfer.recipient_call, variable='XIVO_TRANSFER', value='')

    def cancel(self, transfer_id):
        transfer = self.get(transfer_id)

        self.ari.channels.hangup(channelId=transfer.recipient_call)

        self.ari.channels.unmute(channelId=transfer.transferred_call, direction='in')
        self.ari.channels.unhold(channelId=transfer.transferred_call)
        self.ari.channels.stopMoh(channelId=transfer.transferred_call)

        self.ari.channels.setChannelVar(channelId=transfer.transferred_call, variable='XIVO_TRANSFER', value='')
        self.ari.channels.setChannelVar(channelId=transfer.recipient_call, variable='XIVO_TRANSFER', value='')
