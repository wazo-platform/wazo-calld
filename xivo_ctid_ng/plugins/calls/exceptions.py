# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
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


class XiVOConfdUnreachable(APIException):

    def __init__(self, xivo_confd_config, error):
        super(XiVOConfdUnreachable, self).__init__(
            status_code=503,
            message='xivo-confd server unreachable',
            error_id='xivo-confd-unreachable',
            details={
                'xivo_confd_config': xivo_confd_config,
                'original_error': str(error),
            }
        )


class AsteriskARIUnreachable(APIException):

    def __init__(self, asterisk_ari_config, error):
        super(AsteriskARIUnreachable, self).__init__(
            status_code=503,
            message='Asterisk ARI server unreachable',
            error_id='asterisk-ari-unreachable',
            details={
                'asterisk_ari_config': asterisk_ari_config,
                'original_error': str(error),
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


class InvalidUserUUID(APIException):

    def __init__(self, user_uuid):
        super(InvalidUserUUID, self).__init__(
            status_code=400,
            message='Invalid user: not found',
            error_id='invalid-user',
            details={
                'user_uuid': user_uuid
            }
        )


class UserHasNoLine(APIException):

    def __init__(self, user_uuid):
        super(UserHasNoLine, self).__init__(
            status_code=400,
            message='Invalid user: user has no line',
            error_id='user-has-no-line',
            details={
                'user_uuid': user_uuid
            }
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
