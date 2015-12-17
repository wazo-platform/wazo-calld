# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
import time

from functools import wraps

logger = logging.getLogger(__name__)


class APIException(Exception):
    def __init__(self, status_code, message, error_id, details=None):
        self.status_code = status_code
        self.message = message
        self.id_ = error_id
        self.details = details or {}


def handle_api_exception(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except APIException as error:
            response = {
                'message': error.message,
                'error_id': error.id_,
                'details': error.details,
                'timestamp': time.time()
            }
            logger.error('%s: %s', error.message, error.details)
            return response, error.status_code
    return wrapper


class ARIUnreachable(Exception):

    def __init__(self):
        super(ARIUnreachable, self).__init__('ARI server unreachable... stopping')
