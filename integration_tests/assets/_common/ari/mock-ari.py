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

import json
import logging
import sys

from flask import Flask
from flask import jsonify
from flask import make_response
from flask import request

_EMPTY_RESPONSES = {
    'bridges': {},
    'channels': {},
    'channel_variable': {},
    'originates': [],
}

app = Flask(__name__)

_requests = []
_responses = {}

logging.basicConfig(level=logging.DEBUG)


def _reset():
    global _requests
    global _responses
    _requests = []
    _responses = dict(_EMPTY_RESPONSES)


@app.before_request
def log_request():
    if not request.path.startswith('/_'):
        path = request.path
        log = {'method': request.method,
               'path': path,
               'query': request.args.items(multi=True),
               'body': request.data,
               'json': request.json,
               'headers': dict(request.headers)}
        _requests.append(log)


@app.route('/_requests', methods=['GET'])
def list_requests():
    return jsonify({'requests': _requests})


@app.route('/_reset', methods=['POST'])
def reset():
    _reset()
    return '', 204


@app.route('/_set_response', methods=['POST'])
def set_response():
    global _responses
    request_body = json.loads(request.data)
    set_response = request_body['response']
    set_response_body = request_body['content']
    _responses[set_response] = set_response_body
    return '', 204


@app.route('/ari/api-docs/<path:file_name>')
def swagger(file_name):
    with open('/usr/local/share/ari/api-docs/{file_name}'.format(file_name=file_name), 'r') as swagger_file:
        swagger_spec = swagger_file.read()
        swagger_spec = swagger_spec.replace('localhost:8088', 'ari:{port}'.format(port=port))
        return make_response(swagger_spec, 200, {'Content-Type': 'application/json'})


@app.route('/ari/channels', methods=['GET'])
def get_channels():
    result = [channel for channel in _responses['channels'].itervalues()]
    return make_response(json.dumps(result), 200, {'Content-Type': 'application/json'})


@app.route('/ari/channels', methods=['POST'])
def originate():
    return jsonify(_responses['originates'].pop())


@app.route('/ari/channels/<channel_id>', methods=['GET'])
def get_channel(channel_id):
    if channel_id not in _responses['channels']:
        return '', 404
    return jsonify(_responses['channels'][channel_id])


@app.route('/ari/channels/<channel_id>', methods=['DELETE'])
def delete_channel(channel_id):
    if channel_id not in _responses['channels']:
        return '', 404
    del _responses['channels'][channel_id]
    return '', 204


@app.route('/ari/bridges')
def bridges():
    result = [bridge for bridge in _responses['bridges'].itervalues()]
    return make_response(json.dumps(result), 200, {'Content-Type': 'application/json'})


@app.route('/ari/bridges/<bridge_id>')
def bridge(bridge_id):
    return jsonify(_responses['bridges'][bridge_id])


@app.route('/ari/channels/<channel_id>/variable')
def channel_variable(channel_id):
    variable = request.args['variable']
    if channel_id not in _responses['channel_variable']:
        return '', 404
    if variable not in _responses['channel_variable'][channel_id]:
        return '', 404
    return jsonify({
        'value': _responses['channel_variable'][channel_id][variable]
    })


if __name__ == '__main__':
    _reset()

    port = int(sys.argv[1])
    app.run(host='0.0.0.0', port=port, debug=True)
    # context = ('/usr/local/share/ssl/ari/server.crt', '/usr/local/share/ssl/ari/server.key')
    # app.run(host='0.0.0.0', port=port, ssl_context=context, debug=True)
