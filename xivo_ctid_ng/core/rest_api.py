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
from xivo_ctid_ng.core import plugin_manager

VERSION = 1.0

logger = logging.getLogger(__name__)
app = Flask('xivo_ctid_ng')
api = Api(prefix='/{}'.format(VERSION))
auth_verifier = AuthVerifier()


class CoreRestApi(object):

    def __init__(self, global_config, token_changed_subscribe):
        self.config = global_config['rest_api']
        http_helpers.add_logger(app, logger)
        app.after_request(http_helpers.log_request)
        app.secret_key = os.urandom(24)
        app.permanent_session_lifetime = timedelta(minutes=5)
        auth_verifier.set_config(global_config['auth'])
        self._load_cors()
        self._load_plugins(global_config, token_changed_subscribe)
        api.init_app(app)

    def _load_cors(self):
        cors_config = dict(self.config.get('cors', {}))
        enabled = cors_config.pop('enabled', False)
        if enabled:
            CORS(app, **cors_config)

    def _load_plugins(self, global_config, token_changed_subscribe):
        load_args = [{
            'config': global_config,
            'api': api,
            'token_changed_subscribe': token_changed_subscribe,
        }]
        plugin_manager.load_plugins(global_config['enabled_plugins'], load_args)

    def run(self):
        bind_addr = (self.config['listen'], self.config['port'])

        _check_file_readable(self.config['certificate'])
        _check_file_readable(self.config['private_key'])
        wsgi_app = wsgiserver.WSGIPathInfoDispatcher({'/': app})
        server = wsgiserver.CherryPyWSGIServer(bind_addr=bind_addr,
                                               wsgi_app=wsgi_app)
        server.ssl_adapter = http_helpers.ssl_adapter(self.config['certificate'],
                                                      self.config['private_key'],
                                                      self.config.get('ciphers'))
        logger.debug('WSGIServer starting... uid: %s, listen: %s:%s', os.getuid(), bind_addr[0], bind_addr[1])
        for route in http_helpers.list_routes(app):
            logger.debug(route)

        try:
            server.start()
        except KeyboardInterrupt:
            server.stop()


def _check_file_readable(file_path):
    with open(file_path, 'r'):
        pass


class ErrorCatchingResource(Resource):
    method_decorators = [exceptions.handle_api_exception] + Resource.method_decorators


class AuthResource(ErrorCatchingResource):
    method_decorators = [auth_verifier.verify_token] + ErrorCatchingResource.method_decorators
