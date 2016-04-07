# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from .exceptions import InvalidTransferRecipientCalledEvent
from .exceptions import InvalidCreateTransferEvent

logger = logging.getLogger(__name__)


class TransferRecipientCalledEvent(object):

    def __init__(self, event):
        try:
            self.transfer_bridge = event['args'][2]
        except (KeyError, IndexError):
            raise InvalidTransferRecipientCalledEvent(event)


class CreateTransferEvent(object):

    def __init__(self, event):
        try:
            self.transfer_id = event['args'][2]
        except (KeyError, IndexError):
            raise InvalidCreateTransferEvent(event)
