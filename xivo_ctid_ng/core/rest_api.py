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

import ari
import logging
import os
import requests

from cherrypy import wsgiserver
from flask import current_app
from flask import Flask
from flask import request
from flask_restful import Api
from flask_restful import Resource
from flask_cors import CORS
from contextlib import contextmanager
from werkzeug.contrib.fixers import ProxyFix
from xivo import http_helpers
from xivo_amid_client import Client as AmidClient
from xivo_ctid_ng.core import exceptions
from xivo_ctid_ng.core.exceptions import APIException

VERSION = 1.0

logger = logging.getLogger(__name__)
api = Api(prefix='/{}'.format(VERSION))


class CoreRestApi(object):

    def __init__(self, config):
        self.config = config
        self.app = Flask('xivo_ctid_ng')
        http_helpers.add_logger(self.app, logger)
        self.app.after_request(http_helpers.log_request)
        self.app.wsgi_app = ProxyFix(self.app.wsgi_app)
        self.app.secret_key = os.urandom(24)
        self.app.permanent_session_lifetime = timedelta(minutes=5)
        self.load_cors()
        self.api = api

    def load_cors(self):
        cors_config = dict(self.config.get('cors', {}))
        enabled = cors_config.pop('enabled', False)
        if enabled:
            CORS(self.app, **cors_config)

    def run(self):
        api.add_resource(Calls, '/calls')
        api.add_resource(Call, '/calls/<call_id>')
        self.api.init_app(self.app)

        bind_addr = (self.config['listen'], self.config['port'])

        _check_file_readable(self.config['certificate'])
        _check_file_readable(self.config['private_key'])
        wsgi_app = wsgiserver.WSGIPathInfoDispatcher({'/': self.app})
        server = wsgiserver.CherryPyWSGIServer(bind_addr=bind_addr,
                                               wsgi_app=wsgi_app)
        server.ssl_adapter = http_helpers.ssl_adapter(self.config['certificate'],
                                                      self.config['private_key'],
                                                      self.config.get('ciphers'))
        logger.debug('WSGIServer starting... uid: %s, listen: %s:%s', os.getuid(), bind_addr[0], bind_addr[1])
        for route in http_helpers.list_routes(self.app):
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


def endpoint_from_user_uuid(_):
    return 'SCCP/101'


@contextmanager
def new_amid_client(config):
    yield AmidClient(**config)


@contextmanager
def new_ari_client(config):
    yield ari.connect(**config)


class NoSuchCall(APIException):

    def __init__(self, call_id):
        super(NoSuchCall, self).__init__(
            status_code=404,
            message='No such call',
            error_id='no-such-call',
            details={
                'call_id': call_id
            }
        )


class Calls(ErrorCatchingResource):

    def post(self):
        request_body = request.json
        endpoint = endpoint_from_user_uuid(request_body['source']['user'])
        call_id = '12345'
        params = {
            'Channel': endpoint,
            'Exten': request_body['destination']['extension'],
            'Context': request_body['destination']['context'],
            'Priority': request_body['destination']['priority'],
            'Async': 'True',
            'ChannelId': call_id,
        }
        with new_amid_client(current_app.config['ami']) as amid:
            amid.action('Originate', params, token='e92c1e51-b0a9-5f95-738c-a46a47313340')

        return {'call_id': call_id}, 201


class Call(ErrorCatchingResource):

    def get(self, call_id):
        with new_ari_client(current_app.config['ari']['connection']) as ari:
            try:
                channel = ari.channels.get(channelId=call_id)
            except requests.RequestException:
                raise NoSuchCall(call_id)

            bridges = [bridge.id for bridge in ari.bridges.list() if channel.id in bridge.json['channels']]

            talking_to = set()
            for bridge_id in bridges:
                calls = ari.bridges.get(bridgeId=bridge_id).json['channels']
                talking_to.update(calls)
            talking_to.remove(call_id)

        status = channel.json['state']

        return {
            'status': status,
            'talking_to': list(talking_to),
            'bridges': bridges,
        }
