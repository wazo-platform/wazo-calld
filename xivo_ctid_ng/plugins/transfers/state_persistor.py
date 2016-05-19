# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import json
import logging

from ari.exceptions import ARINotFound

from .transfer import Transfer

logger = logging.getLogger(__name__)

TRANSFERS_INDEX_VAR_NAME = 'XIVO_TRANSFERS_INDEX'


class StatePersistor(object):
    def __init__(self, ari):
        self._ari = ari

    def get(self, transfer_id):
        try:
            entry_str = self._ari.asterisk.getGlobalVar(variable=self._var_name(transfer_id))['value']
        except ARINotFound:
            raise KeyError(transfer_id)
        if not entry_str:
            raise KeyError(transfer_id)

        return Transfer.from_dict(json.loads(entry_str))

    def get_by_channel(self, channel_id):
        try:
            return next(transfer for transfer in self._list()
                        if (channel_id in (transfer.transferred_call,
                                           transfer.initiator_call,
                                           transfer.recipient_call)))
        except StopIteration:
            raise KeyError(channel_id)

    def upsert(self, transfer):
        self._ari.asterisk.setGlobalVar(variable=self._var_name(transfer.id), value=json.dumps(transfer.to_dict()))
        index = self._index()
        index.add(transfer.id)
        self._set_index(index)

    def remove(self, transfer_id):
        self._ari.asterisk.setGlobalVar(variable=self._var_name(transfer_id), value='')
        index = self._index()
        try:
            index.remove(transfer_id)
        except KeyError:
            return
        self._set_index(index)

    def _var_name(self, transfer_id):
        return 'XIVO_TRANSFERS_{}'.format(transfer_id)

    def _index(self):
        try:
            index_str = self._ari.asterisk.getGlobalVar(variable=TRANSFERS_INDEX_VAR_NAME)['value']
        except ARINotFound:
            return set()
        if not index_str:
            return set()
        return set(json.loads(index_str))

    def _list(self):
        for transfer_id in self._index():
            yield self.get(transfer_id)

    def _set_index(self, index):
        self._ari.asterisk.setGlobalVar(variable=TRANSFERS_INDEX_VAR_NAME, value=json.dumps(list(index)))
