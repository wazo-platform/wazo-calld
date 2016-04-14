# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from .exceptions import InvalidEvent

logger = logging.getLogger(__name__)


class TransferRecipientAnsweredEvent(object):

    def __init__(self, event):
        try:
            self.transfer_bridge = event['args'][2]
        except (KeyError, IndexError):
            raise InvalidEvent(event)


class CreateTransferEvent(object):

    def __init__(self, event):
        try:
            self.transfer_id = event['args'][2]
        except (KeyError, IndexError):
            raise InvalidEvent(event)
