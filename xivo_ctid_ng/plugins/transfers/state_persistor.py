# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo_ctid_ng.core.ari_helpers import (GlobalVariableAdapter,
                                           GlobalVariableJsonAdapter,
                                           GlobalVariableNameDecorator,
                                           GlobalVariableConstantNameAdapter)
from .transfer import Transfer

logger = logging.getLogger(__name__)


class StatePersistor(object):
    def __init__(self, ari):
        self._transfers = GlobalVariableNameDecorator(GlobalVariableJsonAdapter(GlobalVariableAdapter(ari)),
                                                      'XIVO_TRANSFERS_{}')
        self._index = GlobalVariableConstantNameAdapter(GlobalVariableJsonAdapter(GlobalVariableAdapter(ari)),
                                                        'XIVO_TRANSFERS_INDEX')

    def get(self, transfer_id):
        return Transfer.from_dict(self._transfers.get(transfer_id))

    def get_by_channel(self, channel_id):
        for transfer in self._list():
            if channel_id in (transfer.transferred_call,
                              transfer.initiator_call,
                              transfer.recipient_call):
                return transfer
        else:
            raise KeyError(channel_id)

    def upsert(self, transfer):
        self._transfers.set(transfer.id, transfer.to_dict())
        index = set(self._index.get(default=[]))
        index.add(transfer.id)
        self._index.set(list(index))

    def remove(self, transfer_id):
        self._transfers.unset(transfer_id)
        index = set(self._index.get(default=[]))
        try:
            index.remove(transfer_id)
        except KeyError:
            return
        self._index.set(list(index))

    def _list(self):
        for transfer_id in self._index.get():
            yield self.get(transfer_id)
