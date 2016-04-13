# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import json
import logging

from ari.exceptions import ARINotFound

from .transfer import Transfer

logger = logging.getLogger(__name__)


class StatePersistor(object):
    global_var_name = 'XIVO_TRANSFERS'

    def __init__(self, ari):
        self._ari = ari

    def get(self, transfer_id):
        return Transfer.from_dict(self._cache()[transfer_id])

    def get_by_channel(self, channel_id):
        try:
            entry = next(transfer for (transfer_id, transfer) in self._cache().iteritems()
                         if (channel_id in (transfer['transferred_call'],
                                            transfer['initiator_call'],
                                            transfer['recipient_call'])))
        except StopIteration:
            raise KeyError(channel_id)
        return Transfer.from_dict(entry)

    def upsert(self, transfer):
        cache = self._cache()
        cache[transfer.id] = transfer.to_dict()
        self._set_cache(cache)

    def remove(self, transfer_id):
        cache = self._cache()
        cache.pop(transfer_id, None)
        self._set_cache(cache)

    def _cache(self):
        try:
            cache_str = self._ari.asterisk.getGlobalVar(variable=self.global_var_name)['value']
        except ARINotFound:
            return {}
        if not cache_str:
            return {}
        return json.loads(cache_str)

    def _set_cache(self, cache):
        self._ari.asterisk.setGlobalVar(variable=self.global_var_name,
                                        value=json.dumps(cache))
