# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from requests import HTTPError
from xivo import rest_api_helpers

logger = logging.getLogger(__name__)


APIException = rest_api_helpers.APIException


class ARIUnreachable(Exception):

    def __init__(self, ari_config, original_error=None):
        super(ARIUnreachable, self).__init__('ARI server unreachable... stopping')
        self.ari_config = ari_config
        self.original_error = original_error


class ARIHTTPError(HTTPError):
    def __init__(self, http_error):
        self.response = http_error.response


class ARINotFound(ARIHTTPError):
    pass


class ARINotInStasis(ARIHTTPError):
    pass


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
