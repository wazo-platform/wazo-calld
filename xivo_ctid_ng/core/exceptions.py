# -*- coding: utf-8 -*-
# Copyright (C) 2015 Avencall
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

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
