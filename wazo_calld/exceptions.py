# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from xivo import rest_api_helpers

logger = logging.getLogger(__name__)


APIException = rest_api_helpers.APIException


class XiVOAmidError(APIException):

    def __init__(self, xivo_amid_client, error):
        super().__init__(
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


class XiVOConfdUnreachable(APIException):

    def __init__(self, confd_client, error):
        super().__init__(
            status_code=503,
            message='xivo-confd server unreachable',
            error_id='xivo-confd-unreachable',
            details={
                'xivo_confd_config': {'host': confd_client.host,
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
