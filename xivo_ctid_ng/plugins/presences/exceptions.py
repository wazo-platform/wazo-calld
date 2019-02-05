# Copyright 2016-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_ctid_ng.exceptions import APIException


class XiVOWebsocketdError(APIException):

    def __init__(self, xivo_websocketd_client, error):
        super().__init__(
            status_code=503,
            message='xivo-websocketd request error',
            error_id='xivo-websocketd-error',
            details={
                'xivo_websocketd_config': {'host': xivo_websocketd_client._host,
                                           'port': xivo_websocketd_client._port,
                                           'verify_certificate': xivo_websocketd_client._verify_certificate},
                'original_error': str(error),
            }
        )


class InvalidCredentials(APIException):

    def __init__(self, xivo_uuid):
        super().__init__(
            status_code=502,
            message='invalid credentials cannot authenticate',
            error_id='invalid-credentials',
            details={
                'xivo_uuid': xivo_uuid,
            },
        )


class MissingCredentials(APIException):

    def __init__(self, xivo_uuid):
        super().__init__(
            status_code=400,
            message='missing credentials cannot authenticate',
            error_id='missing-credentials',
            details={
                'xivo_uuid': xivo_uuid,
            },
        )


class NoSuchLine(APIException):

    def __init__(self, xivo_uuid, line_id):
        super().__init__(
            status_code=404,
            message='no such line',
            error_id='no-such-line',
            details={
                'line_id': line_id,
                'xivo_uuid': xivo_uuid,
            },
        )


class NoSuchUser(APIException):

    def __init__(self, xivo_uuid, user_uuid):
        super().__init__(
            status_code=404,
            message='no such user',
            error_id='no-such-user',
            details={
                'xivo_uuid': xivo_uuid,
                'user_uuid': user_uuid,
            },
        )


class WazoAuthUnreachable(APIException):

    def __init__(self, xivo_uuid, error):
        super().__init__(
            status_code=503,
            message='wazo-auth server unreachable',
            error_id='wazo-auth-unreachable',
            details={
                'xivo_uuid': xivo_uuid,
                'original_error': str(error),
                'service': 'wazo-auth',
            }
        )


class XiVOCtidNgUnreachable(APIException):

    def __init__(self, xivo_uuid, error):
        super().__init__(
            status_code=503,
            message='xivo-ctid-ng server unreachable',
            error_id='xivo-ctid-ng-unreachable',
            details={
                'xivo_uuid': xivo_uuid,
                'original_error': str(error),
                'service': 'xivo-ctid-ng',
            }
        )


class XiVOCtidUnreachable(APIException):

    def __init__(self, xivo_ctid_config, error):
        super().__init__(
            status_code=503,
            message='xivo-ctid server unreachable',
            error_id='xivo-ctid-unreachable',
            details={
                'xivo_ctid_config': xivo_ctid_config,
                'original_error': str(error),
                'service': 'xivo-ctid',
            }
        )
