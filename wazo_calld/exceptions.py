# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from xivo import rest_api_helpers

logger = logging.getLogger(__name__)


APIException = rest_api_helpers.APIException


class InvalidListParamException(APIException):
    def __init__(self, message, details=None):
        super().__init__(400, message, 'invalid-list-param', details, 'users')

    @classmethod
    def from_errors(cls, errors):
        for field, infos in errors.items():
            if not isinstance(infos, list):
                infos = [infos]
            for info in infos:
                return cls(info['message'], {field: info})


class CalldUninitializedError(APIException):

    def __init__(self):
        super().__init__(
            status_code=503,
            message='wazo-calld is not ready to handle this request',
            error_id='wazo-calld-uninitialized',
        )


class WazoAmidError(APIException):

    def __init__(self, wazo_amid_client, error):
        super().__init__(
            status_code=503,
            message='wazo-amid request error',
            error_id='wazo-amid-error',
            details={
                'wazo_amid_config': {'host': wazo_amid_client.host,
                                     'port': wazo_amid_client.port,
                                     'timeout': wazo_amid_client.timeout},
                'original_error': str(error),
            }
        )


class ARIUnreachable(Exception):

    def __init__(self, ari_config, original_error=None):
        super().__init__('ARI server unreachable... stopping')
        self.ari_config = ari_config
        self.original_error = original_error


class AsteriskARIUnreachable(APIException):

    def __init__(self, asterisk_ari_config, error):
        super().__init__(
            status_code=503,
            message='Asterisk ARI server unreachable',
            error_id='asterisk-ari-unreachable',
            details={
                'asterisk_ari_config': asterisk_ari_config,
                'original_error': str(error),
            }
        )


class AsteriskARIError(APIException):

    def __init__(self, asterisk_ari_config, error):
        super().__init__(
            status_code=503,
            message='Asterisk ARI internal error',
            error_id='asterisk-ari-error',
            details={
                'asterisk_ari_config': asterisk_ari_config,
                'original_error': str(error),
            }
        )


class TokenWithUserUUIDRequiredError(APIException):

    def __init__(self):
        super().__init__(
            status_code=400,
            message='A valid token with a user UUID is required',
            error_id='token-with-user-uuid-required',
        )


class WazoConfdError(APIException):

    def __init__(self, confd_client, error):
        super().__init__(
            status_code=503,
            message='wazo-confd error',
            error_id='wazo-confd-error',
            details={
                'wazo_confd_config': {'host': confd_client.host,
                                      'port': confd_client.port,
                                      'timeout': confd_client.timeout},
                'original_error': str(error),
            }
        )


class WazoConfdUnreachable(APIException):

    def __init__(self, confd_client, error):
        super().__init__(
            status_code=503,
            message='wazo-confd server unreachable',
            error_id='wazo-confd-unreachable',
            details={
                'wazo_confd_config': {'host': confd_client.host,
                                      'port': confd_client.port,
                                      'timeout': confd_client.timeout},
                'original_error': str(error),
            }
        )


class UserPermissionDenied(APIException):

    def __init__(self, user_uuid, details):
        details = dict(details)
        details['user'] = user_uuid
        super().__init__(
            status_code=403,
            message='User does not have permission to handle objects of other users',
            error_id='user-permission-denied',
            details=details
        )


class InvalidExtension(APIException):

    def __init__(self, context, exten):
        super().__init__(
            status_code=400,
            message='Invalid extension',
            error_id='invalid-extension',
            details={
                'context': context,
                'exten': exten,
            }
        )
