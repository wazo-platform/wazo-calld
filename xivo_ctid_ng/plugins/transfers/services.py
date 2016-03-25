# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import requests

from xivo_ctid_ng.core.ari_ import APPLICATION_NAME
from xivo_ctid_ng.core.ari_ import not_found

from .exceptions import TransferError


class TransfersService(object):
    def __init__(self, ari):
        self.ari = ari

    def create(self,
               transferred_call,
               initiator_call,
               context,
               exten):
        holding_bridge = self.ari.bridges.create(type='holding')
        holding_bridge.addChannel(channel=transferred_call)
        try:
            app_instance = self.ari.channels.getChannelVar(channelId=initiator_call, variable='XIVO_STASIS_ARGS')['value']
        except requests.HTTPError as e:
            if not_found(e):
                raise TransferError('{call}: no app_instance found'.format(call=initiator_call))
            raise
        recipient_endpoint = 'Local/{exten}@{context}'.format(exten=exten, context=context)
        app_args = [app_instance, 'transfer_recipient_called', initiator_call]
        recipient_channel = self.ari.channels.originate(endpoint=recipient_endpoint,
                                                        app=APPLICATION_NAME,
                                                        appArgs=app_args)

        return recipient_channel.id
