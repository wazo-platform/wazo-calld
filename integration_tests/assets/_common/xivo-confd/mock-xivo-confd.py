# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import json
import logging
import sys

from flask import Flask
from flask import jsonify
from flask import request

logging.basicConfig(level=logging.DEBUG)

_EMPTY_RESPONSES = {
    'users': {},
    'lines': {},
    'user_lines': {},
}

app = Flask(__name__)

_requests = []
_responses = {}


def _reset():
    global _requests
    global _responses
    _requests = []
    _responses = dict(_EMPTY_RESPONSES)


@app.before_request
def log_request():
    if not request.path.startswith('/_requests'):
        path = request.path
        log = {'method': request.method,
               'path': path,
               'query': request.args.items(multi=True),
               'body': request.data,
               'headers': dict(request.headers)}
        _requests.append(log)


@app.route('/_requests', methods=['GET'])
def list_requests():
    return jsonify(requests=_requests)


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


@app.route('/1.1/users/<user_uuid>')
def user(user_uuid):
    if user_uuid not in _responses['users']:
        return '', 404
    return jsonify(_responses['users'][user_uuid])


@app.route('/1.1/lines/<line_id>')
def line(line_id):
    if line_id not in _responses['lines']:
        return '', 404
    return jsonify(_responses['lines'][line_id])


@app.route('/1.1/users/<user_uuid>/lines')
def lines_of_user(user_uuid):
    if user_uuid not in _responses['user_lines']:
        return '', 404

    return jsonify({
        'items': _responses['user_lines'][user_uuid]
    })


if __name__ == '__main__':
    _reset()

    port = int(sys.argv[1])
    context = ('/usr/local/share/ssl/confd/server.crt', '/usr/local/share/ssl/confd/server.key')
    app.run(host='0.0.0.0', port=port, ssl_context=context, debug=True)
