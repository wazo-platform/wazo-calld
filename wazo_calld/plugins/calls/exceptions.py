# Copyright 2015-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_calld.exceptions import APIException


class NoSuchCall(APIException):
    def __init__(self, call_id):
        super().__init__(
            status_code=404,
            message='No such call',
            error_id='no-such-call',
            details={'call_id': call_id},
        )


class CallCreationError(APIException):
    def __init__(self, message, details=None):
        details = details or {}
        super().__init__(
            status_code=400, message=message, error_id='call-creation', details=details
        )


class CallConnectError(APIException):
    def __init__(self, call_id):
        super().__init__(
            status_code=400,
            message='Could not connect call: call has no application instance',
            error_id='call-connect',
            details={'call_id': call_id},
        )


class InvalidCallEvent(RuntimeError):
    pass


class InvalidStartCallEvent(InvalidCallEvent):
    pass


class InvalidConnectCallEvent(InvalidStartCallEvent):
    pass
