# Copyright 2016-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from wazo_calld.helpers import threading
from wazo_calld.plugin_helpers.ari_ import (
    GlobalVariableAdapter,
    GlobalVariableJsonAdapter,
    GlobalVariableNameDecorator,
    GlobalVariableConstantNameAdapter,
)
from .transfer import Transfer

logger = logging.getLogger(__name__)


class StatePersistor:
    def __init__(self, ari):
        self._transfers = GlobalVariableNameDecorator(GlobalVariableJsonAdapter(GlobalVariableAdapter(ari)),
                                                      'XIVO_TRANSFERS_{}')
        self._index = GlobalVariableConstantNameAdapter(GlobalVariableJsonAdapter(GlobalVariableAdapter(ari)),
                                                        'XIVO_TRANSFERS_INDEX')
        self._lock = threading.RLock()

    def get(self, transfer_id):
        with self._lock:
            transfer_dict = self._transfers.get(transfer_id)
        return Transfer.from_dict(transfer_dict)

    def get_by_channel(self, channel_id):
        for transfer in self.list():
            if channel_id in (transfer.transferred_call,
                              transfer.initiator_call,
                              transfer.recipient_call):
                return transfer
        else:
            raise KeyError(channel_id)

    def upsert(self, transfer):
        logger.debug('transfer: %s upsert starting', transfer.id)
        with self._lock:
            self._transfers.set(transfer.id, transfer.to_dict())
            index = set(self._index.get(default=[]))
            index.add(transfer.id)
            self._index.set(list(index))
        logger.debug('transfer: %s upsert done', transfer.id)

    def remove(self, transfer_id):
        logger.debug('transfer: %s remove starting', transfer_id)
        with self._lock:
            self._transfers.unset(transfer_id)
            index = set(self._index.get(default=[]))
            try:
                index.remove(transfer_id)
            except KeyError:
                logger.debug('transfer: %s remove done, not found', transfer_id)
                return
            self._index.set(list(index))
        logger.debug('transfer: %s remove done', transfer_id)

    def list(self):
        results = []
        with self._lock:
            for transfer_id in self._index.get(default=[]):
                try:
                    transfer = self.get(transfer_id)
                except KeyError:
                    logger.debug('transfer list: transfer %s found in index, but details not found', transfer_id)
                    continue
                results.append(transfer)
        return results
