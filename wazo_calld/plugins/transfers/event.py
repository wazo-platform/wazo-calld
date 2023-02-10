# Copyright 2016-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from .exceptions import InvalidEvent

logger = logging.getLogger(__name__)


class TransferRecipientAnsweredEvent:
    def __init__(self, event):
        try:
            self.transfer_bridge = event['args'][2]
        except (KeyError, IndexError):
            raise InvalidEvent(event)


class CreateTransferEvent:
    def __init__(self, event):
        try:
            self.transfer_id = event['args'][2]
        except (KeyError, IndexError):
            raise InvalidEvent(event)
