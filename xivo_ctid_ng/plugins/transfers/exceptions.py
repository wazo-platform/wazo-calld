# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.core.exceptions import APIException


class TranferError(RuntimeError):
    pass


class InvalidTransferRecipientCalledEvent(ValueError):
    pass


class TransferError(Exception):
    pass


class NoSuchTransfer(APIException):

    def __init__(self, transfer_id):
        super(NoSuchTransfer, self).__init__(
            status_code=404,
            message='No such transfer',
            error_id='no-such-transfer',
            details={
                'transfer_id': transfer_id
            }
        )
