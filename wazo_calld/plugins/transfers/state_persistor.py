# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from wazo_calld.helpers.ari_ import (GlobalVariableAdapter,
                                     GlobalVariableJsonAdapter,
                                     GlobalVariableNameDecorator,
                                     GlobalVariableConstantNameAdapter)
from .transfer import Transfer

logger = logging.getLogger(__name__)


class StatePersistor:
    def __init__(self, ari):
        self._transfers = GlobalVariableNameDecorator(GlobalVariableJsonAdapter(GlobalVariableAdapter(ari)),
                                                      'XIVO_TRANSFERS_{}')
        self._index = GlobalVariableConstantNameAdapter(GlobalVariableJsonAdapter(GlobalVariableAdapter(ari)),
                                                        'XIVO_TRANSFERS_INDEX')

    def get(self, transfer_id):
        return Transfer.from_dict(self._transfers.get(transfer_id))

    def get_by_channel(self, channel_id):
        for transfer in self.list():
            if channel_id in (transfer.transferred_call,
                              transfer.initiator_call,
                              transfer.recipient_call):
                return transfer
        else:
            raise KeyError(channel_id)

    def upsert(self, transfer):
        self._transfers.set(transfer.id, transfer.to_dict())
        logger.debug('transfer: %s upsert starting', transfer.id)
        index = set(self._index.get(default=[]))
        index.add(transfer.id)
        self._index.set(list(index))
        logger.debug('transfer: %s upsert done', transfer.id)

    def remove(self, transfer_id):
        self._transfers.unset(transfer_id)
        logger.debug('transfer: %s remove starting', transfer_id)
        index = set(self._index.get(default=[]))
        try:
            index.remove(transfer_id)
        except KeyError:
            logger.debug('transfer: %s remove done, not found', transfer_id)
            return
        self._index.set(list(index))
        logger.debug('transfer: %s remove done', transfer_id)

    def list(self):
        for transfer_id in self._index.get(default=[]):
            yield self.get(transfer_id)
