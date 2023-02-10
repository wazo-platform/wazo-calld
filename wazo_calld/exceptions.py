# Copyright 2015-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from xivo import rest_api_helpers

logger = logging.getLogger(__name__)


APIException = rest_api_helpers.APIException


class ARIUnreachable(Exception):
    def __init__(self, ari_config, original_error=None):
        super().__init__('ARI server unreachable... stopping')
        self.ari_config = ari_config
        self.original_error = original_error


class AsteriskARIUnreachable(APIException):
    def __init__(self, asterisk_ari_config, original_error, original_message):
        super().__init__(
            status_code=503,
            message='Asterisk ARI server unreachable',
            error_id='asterisk-ari-unreachable',
            details={
                'asterisk_ari_config': asterisk_ari_config,
                'original_error': f'{original_error}: {original_message}',
            },
        )


class AsteriskARIError(APIException):
    def __init__(self, asterisk_ari_config, original_error, original_message):
        super().__init__(
            status_code=503,
            message='Asterisk ARI internal error',
            error_id='asterisk-ari-error',
            details={
                'asterisk_ari_config': asterisk_ari_config,
                'original_error': f'{original_error}: {original_message}',
            },
        )


class AsteriskARINotInitialized(APIException):
    def __init__(self):
        super().__init__(
            status_code=503,
            message='Asterisk ARI client not initialized',
            error_id='asterisk-ari-not-initialized',
        )


class TokenWithUserUUIDRequiredError(APIException):
    def __init__(self):
        super().__init__(
            status_code=400,
            message='A valid token with a user UUID is required',
            error_id='token-with-user-uuid-required',
        )


class PhonedError(APIException):
    def __init__(self, phoned_config, error):
        super().__init__(
            status_code=503,
            message='Phoned internal error',
            error_id='phoned-error',
            details={
                'phoned_config': phoned_config,
                'original_error': str(error),
            },
        )


class MasterTenantNotInitialized(APIException):
    def __init__(self):
        msg = 'wazo-calld master tenant is not initialized'
        super().__init__(503, msg, 'master-tenant-not-initialized')
