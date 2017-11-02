# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import json
import logging
import sys

from flask import Flask
from flask_sockets import Sockets
from flask import jsonify
from flask import make_response
from flask import request

_EMPTY_RESPONSES = {}

app = Flask(__name__)
sockets = Sockets(app)
websocket = None

_requests = []
_responses = {}

logging.basicConfig(level=logging.DEBUG)


def _reset():
    global _requests
    global _responses
    _requests = []
    _responses = {}


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
    logging.critical(_responses)
    return '', 204


@app.route('/_websockets')
def websockets():
    result = []
    if websocket:
        result.append(id(websocket))
    return make_response(json.dumps(result), 200, {'Content-Type': 'application/json'})


@sockets.route('/')
def echo_socket(ws):
    global websocket
    global _requests
    _requests = []
    websocket = ws
    init = {'op': 'init', 'code': 0}
    ws.send(json.dumps(init))
    while True:
        try:
            command = json.loads(ws.receive())
            _requests.append(command)
            response = _responses[command['op']]
            ws.send(json.dumps(response))
        except (KeyError, TypeError, ValueError, Exception):
            websocket = None
            raise
    websocket = None


_reset()


if __name__ == '__main__':
    port = int(sys.argv[1])
    app.run(host='0.0.0.0', port=port, debug=True)
