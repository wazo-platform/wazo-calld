# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
import requests

from flask import request
from flask_restful import abort
from functools import wraps
from time import time

from xivo_auth_client import Client

logger = logging.getLogger(__name__)


def required_acl(acl):
    def wrapper(func):
        func.acl = acl
        return func
    return wrapper


class AuthVerifier(object):

    def __init__(self):
        self._auth_config = None

    def set_config(self, auth_config):
        self._auth_config = dict(auth_config)
        self._auth_config.pop('username', None)
        self._auth_config.pop('password', None)
        self._auth_config.pop('key_file', None)
        self._auth_client = Client(**self._auth_config)

    def verify_token(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            token = request.headers.get('X-Auth-Token', '')

            assert self._auth_client, 'AuthVerifier is not configured'

            try:
                required_acl = getattr(func, 'acl', '').format(**kwargs)
                token_is_valid = self._auth_client.token.is_valid(token, required_acl)
            except requests.RequestException as e:
                auth_host = self._auth_config['host']
                auth_port = self._auth_config['port']
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
