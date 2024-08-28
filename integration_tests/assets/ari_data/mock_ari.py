#!/usr/bin/env python3
# Copyright 2015-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import json
import logging
import sys

from flask import Flask, Response, jsonify, make_response, request
from flask_sockets import Sockets
from geventwebsocket.websocket import WebSocket

_EMPTY_RESPONSES: dict[str, dict | list] = {
    'amqp': {},
    'applications': {},
    'bridges': {},
    'channel_variables': {},
    'channels': {},
    'endpoints': [],
    'global_variables': {},
    'originates': [],
}

app = Flask(__name__)
sockets = Sockets(app)
websocket: WebSocket = None  # type: ignore[assignment]

_requests: list = []
_responses: dict = {}

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('wazo-ari-mock')


def _reset() -> None:
    global _requests
    global _responses
    _requests = []
    _responses = dict(_EMPTY_RESPONSES)


@app.errorhandler(500)
def handle_generic(e: Exception) -> Response:
    logger.error(f'Exception: {e}')
    return jsonify({'error': str(e)})


@app.before_request
def log_request() -> None:
    if not request.path.startswith('/_'):
        path = request.path
        log = {
            'method': request.method,
            'path': path,
            'query': list(request.args.items(multi=True)),
            'body': request.data.decode('utf-8'),
            'json': request.json if request.is_json else None,
            'headers': dict(request.headers),
        }
        _requests.append(log)


@app.route('/_requests', methods=['GET'])
def list_requests() -> Response:
    return jsonify({'requests': _requests})


@app.route('/_reset', methods=['POST'])
def reset() -> tuple[str, int]:
    _reset()
    return '', 204


@app.route('/_set_response', methods=['POST'])
def set_response() -> tuple[str, int]:
    global _responses
    request_body = json.loads(request.data)
    set_response = request_body['response']
    set_response_body = request_body['content']
    _responses[set_response] = set_response_body
    return '', 204


@app.route('/_send_ws_event', methods=['POST'])
def send_event() -> tuple[str, int]:
    websocket.send(request.data)
    return '', 201


@app.route('/_websockets')
def websockets() -> Response:
    result = []
    if websocket:
        result.append(id(websocket))
    return make_response(json.dumps(result), 200, {'Content-Type': 'application/json'})


@app.route('/ari/amqp/<application_name>', methods=['POST'])
def get_amqp(application_name: str) -> Response:
    return jsonify({'foo': 'bar'})


@app.route('/ari/api-docs/<path:file_name>')
def swagger(file_name: str) -> Response:
    with open(f'/usr/local/share/ari/api-docs/{file_name}') as swagger_file:
        swagger_spec = swagger_file.read()
        swagger_spec = swagger_spec.replace(
            'localhost:8088', f'ari:{request.environ["SERVER_PORT"]}'
        )
        return make_response(swagger_spec, 200, {'Content-Type': 'application/json'})


@app.route('/ari/applications/<application_name>', methods=['GET'])
def get_application(application_name: str) -> Response | tuple[str, int]:
    if application_name not in _responses['applications']:
        return '', 404
    return jsonify(_responses['applications'][application_name])


@app.route('/ari/channels', methods=['GET'])
def get_channels() -> Response:
    result = [channel for channel in _responses['channels'].values()]
    return make_response(json.dumps(result), 200, {'Content-Type': 'application/json'})


@app.route('/ari/channels', methods=['POST'])
def originate() -> Response:
    return jsonify(_responses['originates'].pop())


@app.route('/ari/channels/<channel_id>', methods=['GET'])
def get_channel(channel_id) -> Response | tuple[str, int]:
    if channel_id not in _responses['channels']:
        return '', 404
    return jsonify(_responses['channels'][channel_id])


@app.route('/ari/channels/<channel_id>', methods=['DELETE'])
def delete_channel(channel_id) -> tuple[str, int]:
    if channel_id not in _responses['channels']:
        return '', 404
    del _responses['channels'][channel_id]
    return '', 204


@app.route('/ari/channels/<channel_id>/answer', methods=['POST'])
def answer(channel_id) -> tuple[str, int]:
    return '', 204


@app.route('/ari/bridges')
def list_bridges() -> Response:
    result = [bridge for bridge in _responses['bridges'].values()]
    return make_response(json.dumps(result), 200, {'Content-Type': 'application/json'})


@app.route('/ari/bridges/<bridge_id>')
def get_bridge(bridge_id) -> Response:
    return jsonify(_responses['bridges'][bridge_id])


@app.route('/ari/bridges', methods=['POST'])
def post_bridge() -> Response:
    new_bridge = {
        'id': 'bridge-id',
        'technology': 'stasis',
        'bridge_type': 'mixing',
        'creator': 'stasis',
        'bridge_class': 'stasis',
        'name': '',
        'channels': [],
    }
    return jsonify(new_bridge)


@app.route('/ari/bridges/<bridge_id>/addChannel', methods=['POST'])
def add_channel_to_bridge(bridge_id: str) -> tuple[str, int]:
    return '', 204


@app.route('/ari/endpoints')
def list_endpoints() -> Response:
    result = _responses['endpoints']
    return make_response(json.dumps(result), 200, {'Content-Type': 'application/json'})


@app.route('/ari/endpoints/<tech>/<resource>', methods=['GET'])
def get_endpoint(tech: str, resource: str) -> Response | tuple[str, int]:
    for endpoint in _responses['endpoints']:
        if endpoint['technology'] == tech and endpoint['resource'] == resource:
            result = endpoint
            return make_response(
                json.dumps(result), 200, {'Content-Type': 'application/json'}
            )
    return '', 404


@app.route('/ari/channels/<channel_id>/variable', methods=['GET'])
def channel_variable(channel_id: str) -> Response | tuple[str, int]:
    variable = request.args['variable']
    if channel_id not in _responses['channel_variables']:
        return '', 404
    if variable not in _responses['channel_variables'][channel_id]:
        return '', 404
    return jsonify({'value': _responses['channel_variables'][channel_id][variable]})


@app.route('/ari/channels/<channel_id>/variable', methods=['POST'])
def post_channel_variable(channel_id: str) -> tuple[str, int]:
    variable = request.args['variable']
    value = request.args['value']
    if channel_id not in _responses['channels']:
        return '', 404
    if channel_id not in _responses['channel_variables']:
        _responses['channel_variables'][channel_id] = {}
    _responses['channel_variables'][channel_id][variable] = value
    return '', 204


@app.route('/ari/applications/<application_name>/subscription', methods=['POST'])
def subscribe_application(application_name: str) -> Response:
    return jsonify({})


@app.route('/ari/asterisk/variable', methods=['GET'])
def get_global_variable() -> Response | tuple[str, int]:
    variable = request.args['variable']
    if variable not in _responses['global_variables']:
        # Asterisk doesn't raise error when variable doesn't exist
        return jsonify({'value': ''})
    return jsonify({'value': _responses['global_variables'][variable]})


@app.route('/ari/asterisk/variable', methods=['POST'])
def set_global_variable() -> tuple[str, int]:
    variable = request.args['variable']
    value = request.args['value']
    _responses['global_variables'][variable] = value
    return '', 204


@sockets.route('/ari/events')
def echo_socket(ws) -> None:
    global websocket
    websocket = ws
    while True:
        try:
            ws.receive()
        except Exception:
            websocket = None
            raise


_reset()


if __name__ == '__main__':
    port = int(sys.argv[1])
    app.run(host='0.0.0.0', port=port, debug=True)
    # context = ('/usr/local/share/ssl/ari/server.crt', '/usr/local/share/ssl/ari/server.key')
    # app.run(host='0.0.0.0', port=port, ssl_context=context, debug=True)
