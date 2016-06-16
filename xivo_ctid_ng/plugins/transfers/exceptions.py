# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.core.exceptions import APIException


class XiVOAmidError(APIException):

    def __init__(self, xivo_amid_client, error):
        super(XiVOAmidError, self).__init__(
            status_code=503,
            message='xivo-amid request error',
            error_id='xivo-amid-error',
            details={
                'xivo_amid_config': {'host': xivo_amid_client.host,
                                     'port': xivo_amid_client.port,
                                     'timeout': xivo_amid_client.timeout},
                'original_error': str(error),
            }
        )


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


class InvalidExtension(TransferException):

    def __init__(self, context, exten):
        super(InvalidExtension, self).__init__(
            status_code=400,
            message='Invalid extension',
            error_id='invalid-extension',
            details={
                'context': context,
                'exten': exten,
            }
        )


class NoSuchChannel(Exception):
    def __init__(self, channel):
        self.channel = channel


class TooManyChannels(Exception):
    def __init__(self, channels):
        self.channels = channels


class NotEnoughChannels(Exception):
    pass
