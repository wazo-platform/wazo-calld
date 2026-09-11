#!/usr/bin/env python3
# Copyright 2016-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import json
import logging
import sys

from flask import Flask, Response, jsonify, request

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

action_response = ''
queue_status_response: list = []
queue_pause_errors: list = []
valid_extens: list = []
_requests: list = []


def _reset() -> None:
    global _requests
    global action_response
    global queue_status_response
    global queue_pause_errors
    global valid_extens
    _requests = []
    action_response = ''
    queue_status_response = []
    queue_pause_errors = []
    valid_extens = []


@app.errorhandler(500)
def handle_generic(e: Exception) -> Response:
    logger.error(f'Exception: {e}')
    return jsonify({'error': str(e)})


@app.before_request
def log_request():
    global _requests

    if request.path.startswith('/_'):
        return

    log = {
        'method': request.method,
        'path': request.path,
        'query': list(request.args.items(multi=True)),
        'body': request.data.decode('utf-8'),
        'json': request.json if request.is_json else None,
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


@app.route("/_set_queue_status", methods=['POST'])
def set_queue_status():
    global queue_status_response
    queue_status_response = request.get_json()

    return '', 204


@app.route("/_set_queue_pause_error", methods=['POST'])
def set_queue_pause_error():
    global queue_pause_errors
    queue_pause_errors.append(request.get_json())

    return '', 204


@app.route("/1.0/action/<action>", methods=['POST'])
def action(action):
    return json.dumps(action_response), 200


@app.route("/1.0/action/QueueStatus", methods=['POST'])
def queue_status():
    return jsonify(queue_status_response + [{'Event': 'QueueStatusComplete'}]), 200


@app.route("/1.0/action/QueuePause", methods=['POST'])
def queue_pause():
    body = request.get_json()
    for error in queue_pause_errors:
        if error['interface'] != body.get('Interface'):
            continue
        if error['paused'] is not None and error['paused'] != body.get('Paused'):
            continue
        return jsonify([{'Response': 'Error', 'Message': error['message']}]), 200

    return jsonify([{'Response': 'Success'}]), 200


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
