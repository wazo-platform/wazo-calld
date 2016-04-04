# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from .exceptions import InvalidTransferRecipientCalledEvent


class TransferRecipientCalledEvent(object):

    def __init__(self, event):
        try:
            self.transfer_bridge = event['args'][2]
        except (KeyError, IndexError):
            raise InvalidTransferRecipientCalledEvent(event)
