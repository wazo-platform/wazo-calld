# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.exceptions import APIException


class InvalidEvent(ValueError):

    def __init__(self, event):
        self.event = event


class TransferException(APIException):
    pass


class TransferCreationError(TransferException):
    def __init__(self, message):
        super(TransferCreationError, self).__init__(
            status_code=400,
            message='Transfer creation error',
            error_id='transfer-creation-error',
            details={
                'message': message,
            }
        )


class TooManyTransferredCandidates(TransferException):
    def __init__(self, candidates):
        super(TooManyTransferredCandidates, self).__init__(
            status_code=409,
            message='Too many transferred candidates',
            error_id='too-many-transferred-candidates',
            details={
                'candidates': list(candidates),
            }
        )


class TransferAnswerError(TransferException):
    def __init__(self, transfer_id, message):
        super(TransferAnswerError, self).__init__(
            status_code=400,
            message='Transfer answer error',
            error_id='transfer-answer-error',
            details={
                'transfer_id': transfer_id,
                'message': message,
            }
        )


class TransferCompletionError(TransferException):
    def __init__(self, transfer_id, message):
        super(TransferCompletionError, self).__init__(
            status_code=400,
            message='Transfer completion error',
            error_id='transfer-completion-error',
            details={
                'transfer_id': transfer_id,
                'message': message,
            }
        )


class TransferCancellationError(TransferException):
    def __init__(self, transfer_id, message):
        super(TransferCancellationError, self).__init__(
            status_code=400,
            message='Transfer cancellation error',
            error_id='transfer-cancellation-error',
            details={
                'transfer_id': transfer_id,
                'message': message,
            }
        )


class NoSuchTransfer(TransferException):

    def __init__(self, transfer_id):
        super(NoSuchTransfer, self).__init__(
            status_code=404,
            message='No such transfer',
            error_id='no-such-transfer',
            details={
                'transfer_id': transfer_id,
            }
        )


class TransferAlreadyStarted(TransferException):
    def __init__(self, initiator_call):
        super(TransferAlreadyStarted, self).__init__(
            status_code=409,
            message='Transfer already started with same initiator',
            error_id='transfer-already-started',
            details={
                'initiator_call': initiator_call,
            }
        )
