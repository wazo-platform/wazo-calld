# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+


class TranferError(RuntimeError):
    pass


class InvalidTransferRecipientCalledEvent(ValueError):
    pass


class TransferError(Exception):
    pass
