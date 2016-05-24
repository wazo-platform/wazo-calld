# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo_bus.resources.calls.transfer import (CreateTransferEvent)

logger = logging.getLogger(__name__)


class TransferNotifier(object):

    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    def created(self, transfer):
        event = CreateTransferEvent(transfer.to_dict())
        self._bus_producer.publish(event)
