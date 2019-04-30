# Copyright 2017-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_calld.exceptions import APIException


class RelocateException(APIException):
    pass


class RelocateCreationError(RelocateException):
    def __init__(self, message, details=None):
        details = details or {}
        details.setdefault('message', message)
        super().__init__(
            status_code=400,
            message='Relocate creation error',
            error_id='relocate-creation-error',
            details=details
        )


class TooManyChannelCandidates(RelocateException):
    def __init__(self, candidates):
        super().__init__(
            status_code=409,
            message='Too many channels candidates',
            error_id='too-many-channels-candidates',
            details={
                'candidates': list(candidates),
            }
        )


class RelocateAlreadyStarted(RelocateException):
    def __init__(self, initiator_call):
        super().__init__(
            status_code=409,
            message='Relocate already started with same initiator',
            error_id='relocate-already-started',
            details={
                'initiator_call': initiator_call,
            }
        )


class NoSuchRelocate(RelocateException):

    def __init__(self, relocate_id):
        super().__init__(
            status_code=404,
            message='No such relocate',
            error_id='no-such-relocate',
            details={
                'relocate_id': relocate_id,
            }
        )


class RelocateCompletionError(RelocateException):

    def __init__(self, message, details=None):
        details = details or {}
        details.setdefault('message', message)
        super().__init__(
            status_code=400,
            message='Relocate completion error',
            error_id='relocate-completion-error',
            details=details
        )


class RelocateCancellationError(RelocateException):

    def __init__(self, message, details=None):
        details = details or {}
        details.setdefault('message', message)
        super().__init__(
            status_code=400,
            message='Relocate cancellation error',
            error_id='relocate-cancellation-error',
            details=details
        )
