# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.core.exceptions import APIException


class InvalidEvent(ValueError):

    def __init__(self, event):
        self.event = event


class TransferError(RuntimeError):
    pass


class TransferCreationError(TransferError):
    def __init__(self, detail):
        super(TransferCreationError, self).__init__(
            status_code=400,
            message='Transfer creation error',
            error_id='transfer-creation-error',
            details={
                'message': detail,
            }
        )


class TransferCompletionError(TransferError):
    def __init__(self, transfer_id, detail):
        super(TransferCompletionError, self).__init__(
            status_code=400,
            message='Transfer completion error',
            error_id='transfer-completion-error',
            details={
                'transfer_id': transfer_id,
                'message': detail,
            }
        )


class TransferCancellationError(TransferError):
    def __init__(self, transfer_id, detail):
        super(TransferCancellationError, self).__init__(
            status_code=400,
            message='Transfer cancellation error',
            error_id='transfer-cancellation-error',
            details={
                'transfer_id': transfer_id,
                'message': detail,
            }
        )


class NoSuchTransfer(APIException):

    def __init__(self, transfer_id):
        super(NoSuchTransfer, self).__init__(
            status_code=404,
            message='No such transfer',
            error_id='no-such-transfer',
            details={
                'transfer_id': transfer_id,
            }
        )
