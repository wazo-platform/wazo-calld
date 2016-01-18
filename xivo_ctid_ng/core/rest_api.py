# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+


from datetime import timedelta

import logging
import os

from cherrypy import wsgiserver
from flask import Flask
from flask_restful import Api
from flask_restful import Resource
from flask_cors import CORS
from xivo import http_helpers
from xivo_ctid_ng.core.auth import AuthVerifier
from xivo_ctid_ng.core import exceptions

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

    def _load_cors(self):
        cors_config = dict(self.config.get('cors', {}))
        enabled = cors_config.pop('enabled', False)
        if enabled:
            CORS(app, **cors_config)

    def run(self):
        bind_addr = (self.config['listen'], self.config['port'])

        wsgi_app = wsgiserver.WSGIPathInfoDispatcher({'/': app})
        server = wsgiserver.CherryPyWSGIServer(bind_addr=bind_addr,
                                               wsgi_app=wsgi_app)
        server.ssl_adapter = http_helpers.ssl_adapter(self.config['certificate'],
                                                      self.config['private_key'],
                                                      self.config['ciphers'])
        logger.debug('WSGIServer starting... uid: %s, listen: %s:%s', os.getuid(), bind_addr[0], bind_addr[1])
        for route in http_helpers.list_routes(app):
            logger.debug(route)

        try:
            server.start()
        except KeyboardInterrupt:
            server.stop()


class ErrorCatchingResource(Resource):
    method_decorators = [exceptions.handle_api_exception] + Resource.method_decorators


class AuthResource(ErrorCatchingResource):
    method_decorators = [auth_verifier.verify_token] + ErrorCatchingResource.method_decorators
