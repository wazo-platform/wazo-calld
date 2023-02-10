# -*- coding: utf-8 -*-
# Copyright 2016-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import json
import sys

from flask import Flask
from flask import jsonify
from flask import request

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

action_response = ''
valid_extens = []
_requests = []


def _reset():
    global _requests
    global action_response
    global valid_extens
    _requests = []
    action_response = ''
    valid_extens = []


@app.before_request
def log_request():
    global _requests

    if request.path.startswith('/_'):
        return

    log = {
        'method': request.method,
        'path': request.path,
        'query': request.args.items(multi=True),
        'body': request.data,
        'json': request.json,
        'headers': dict(request.headers),
    }
    _requests.append(log)


@app.route('/_reset', methods=['POST'])
def reset():
    _reset()
    return '', 204


@app.route('/_requests', methods=['GET'])
def list_requests():
    return jsonify({'requests': _requests})


@app.route("/_set_action", methods=['POST'])
def set_action():
    global action_response
    action_response = request.get_json()

    return '', 204


@app.route("/_set_valid_exten", methods=['POST'])
def set_valid_exten():
    global valid_extens
    body = request.get_json()
    valid_extens.append((body['context'], body['exten'], body['priority']))
    return '', 204


@app.route("/1.0/action/<action>", methods=['POST'])
def action(action):
    return json.dumps(action_response), 200


@app.route("/1.0/action/ShowDialplan", methods=['POST'])
def show_dialplan():
    global valid_extens
    body = request.get_json()
    requested_context = body['Context']
    requested_exten = body['Extension']

    result = [
        {
            'Event': 'ListDialplan',
            'Context': context,
            'Exten': exten,
            'Priority': str(priority),
        }
        for (context, exten, priority) in valid_extens
        if context == requested_context and exten == requested_exten
    ]

    return json.dumps(result), 200


if __name__ == "__main__":
    port = int(sys.argv[1])
    app.run(host='0.0.0.0', port=port, debug=True)
