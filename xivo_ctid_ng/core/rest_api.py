# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
import os
import marshmallow

from ari.exceptions import ARIException
from ari.exceptions import ARIHTTPError
from cherrypy import wsgiserver
from datetime import timedelta
from flask import Flask
from flask_restful import Api
from flask_restful import Resource
from flask_cors import CORS
from functools import wraps
from xivo.auth_verifier import AuthVerifier
from xivo import http_helpers
from xivo import rest_api_helpers

from .exceptions import AsteriskARIUnreachable
from .exceptions import AsteriskARIError
from .exceptions import ValidationError

VERSION = 1.0

logger = logging.getLogger(__name__)
app = Flask('xivo_ctid_ng')
api = Api(app, prefix='/{}'.format(VERSION))
auth_verifier = AuthVerifier()


class CoreRestApi(object):

    def __init__(self, global_config):
        self.config = global_config['rest_api']
        http_helpers.add_logger(app, logger)
        app.after_request(http_helpers.log_request)
        app.secret_key = os.urandom(24)
        app.permanent_session_lifetime = timedelta(minutes=5)
        auth_verifier.set_config(global_config['auth'])
        self._load_cors()
        self.server = None

    def _load_cors(self):
        cors_config = dict(self.config.get('cors', {}))
        enabled = cors_config.pop('enabled', False)
        if enabled:
            CORS(app, **cors_config)

    def run(self):
        bind_addr = (self.config['listen'], self.config['port'])

        wsgi_app = wsgiserver.WSGIPathInfoDispatcher({'/': app})
        self.server = wsgiserver.CherryPyWSGIServer(bind_addr=bind_addr,
                                                    wsgi_app=wsgi_app)
        self.server.ssl_adapter = http_helpers.ssl_adapter(self.config['certificate'],
                                                           self.config['private_key'],
                                                           self.config['ciphers'])
        logger.debug('WSGIServer starting... uid: %s, listen: %s:%s', os.getuid(), bind_addr[0], bind_addr[1])
        for route in http_helpers.list_routes(app):
            logger.debug(route)

        try:
            self.server.start()
        except KeyboardInterrupt:
            self.server.stop()

    def stop(self):
        if self.server:
            self.server.stop()


def handle_ari_exception(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ARIHTTPError as e:
            raise AsteriskARIError({'base_url': e.client.base_url}, e.original_error)
        except ARIException as e:
            raise AsteriskARIUnreachable({'base_url': e.client.base_url}, e.original_error)
    return wrapper


def handle_validation_exception(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except marshmallow.ValidationError as e:
            raise ValidationError(e.messages)
    return wrapper


class ErrorCatchingResource(Resource):
    method_decorators = ([handle_validation_exception,
                          handle_ari_exception,
                          rest_api_helpers.handle_api_exception] +
                         Resource.method_decorators)


class AuthResource(ErrorCatchingResource):
    method_decorators = [auth_verifier.verify_token] + ErrorCatchingResource.method_decorators
