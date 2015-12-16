# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
import requests

from flask import current_app
from flask import request
from flask_restful import abort
from functools import wraps
from time import time

from xivo_auth_client import Client

logger = logging.getLogger(__name__)


def verify_token(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        token = request.headers.get('X-Auth-Token', '')

        try:
            token_is_valid = client().token.is_valid(token)
        except requests.RequestException as e:
            auth_host = current_app.config['auth']['host']
            auth_port = current_app.config['auth']['port']
            message = 'Could not connect to authentication server on {host}:{port}: {error}'.format(host=auth_host, port=auth_port, error=e)
            logger.exception(message)
            return {
                'reason': [message],
                'timestamp': [time()],
                'status_code': 503,
            }, 503

        if token_is_valid:
            return func(*args, **kwargs)

        abort(401)
    return wrapper


def client():
    auth_host = current_app.config['auth']['host']
    auth_port = current_app.config['auth']['port']
    return Client(auth_host, auth_port)
