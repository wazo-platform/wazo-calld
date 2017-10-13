# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.exceptions import APIException


class RelocateException(APIException):
    pass


class RelocateCreationError(RelocateException):
    def __init__(self, message, details=None):
        details = details or {}
        details.setdefault('message', message)
        super(RelocateCreationError, self).__init__(
            status_code=400,
            message='Relocate creation error',
            error_id='relocate-creation-error',
            details=details
        )


class TooManyChannelCandidates(RelocateException):
    def __init__(self, candidates):
        super(TooManyChannelCandidates, self).__init__(
            status_code=409,
            message='Too many channels candidates',
            error_id='too-many-channels-candidates',
            details={
                'candidates': list(candidates),
            }
        )


class RelocateAlreadyStarted(RelocateException):
    def __init__(self, initiator_call):
        super(RelocateAlreadyStarted, self).__init__(
            status_code=409,
            message='Relocate already started with same initiator',
            error_id='relocate-already-started',
            details={
                'initiator_call': initiator_call,
            }
        )
