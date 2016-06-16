# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.core.exceptions import APIException


class NoSuchCall(APIException):

    def __init__(self, call_id):
        super(NoSuchCall, self).__init__(
            status_code=404,
            message='No such call',
            error_id='no-such-call',
            details={
                'call_id': call_id
            }
        )


class CallCreationError(APIException):

    def __init__(self, message, details=None):
        details = details or {}
        super(CallCreationError, self).__init__(
            status_code=400,
            message=message,
            error_id='call-creation',
            details=details
        )


class CallConnectError(APIException):

    def __init__(self, call_id):
        super(CallConnectError, self).__init__(
            status_code=400,
            message='Could not connect call: call has no application instance',
            error_id='call-connect-error',
            details={
                'call_id': call_id
            }
        )


class InvalidCallEvent(RuntimeError):
    pass


class InvalidStartCallEvent(InvalidCallEvent):
    pass


class InvalidConnectCallEvent(InvalidStartCallEvent):
    pass
