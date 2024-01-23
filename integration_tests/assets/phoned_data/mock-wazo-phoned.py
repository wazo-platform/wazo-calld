#!/usr/bin/env python3
# Copyright 2020-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later
from __future__ import annotations

import logging
import sys

from flask import Flask, Response, jsonify, request

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

action_response = ''
valid_extens = []
_requests = []


def _reset() -> None:
    global _requests
    global action_response
    global valid_extens
    _requests = []
    action_response = ''
    valid_extens = []


@app.before_request
def log_request() -> None:
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
def reset() -> tuple[str, int]:
    _reset()
    return '', 204


@app.route('/_requests', methods=['GET'])
def list_requests() -> Response:
    return jsonify({'requests': _requests})


@app.route("/0.1/endpoints/<endpoint>/hold/start", methods=['PUT'])
def start_hold(endpoint: str) -> tuple[str, int]:
    if endpoint == 'not-found':
        return '', 404
    if endpoint == 'no-plugin':
        return '', 400
    return '', 204


@app.route("/0.1/endpoints/<endpoint>/hold/stop", methods=['PUT'])
def stop_hold(endpoint: str) -> tuple[str, int]:
    if endpoint == 'not-found':
        return '', 404
    if endpoint == 'no-plugin':
        return '', 400
    return '', 204


@app.route("/0.1/endpoints/<endpoint>/answer", methods=['PUT'])
def answer(endpoint):
    if endpoint == 'not-found':
        return '', 404
    if endpoint == 'no-plugin':
        return '', 400
    return '', 204


if __name__ == "__main__":
    port = int(sys.argv[1])
    app.run(host='0.0.0.0', port=port, debug=True)
