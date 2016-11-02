# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
import json
import sys

from flask import Flask
from flask import jsonify
from flask import request

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

context = ('/usr/local/share/ssl/amid/server.crt', '/usr/local/share/ssl/amid/server.key')

action_response = ''
_requests = []


def _reset():
    global _requests
    global action_response
    _requests = []
    action_response = ''


@app.before_request
def log_request():
    global _requests

    if request.path.startswith('/_'):
        return

    log = {'method': request.method,
           'path': request.path,
           'query': request.args.items(multi=True),
           'body': request.data,
           'json': request.json,
           'headers': dict(request.headers)}
    _requests.append(log)


@app.route('/_requests', methods=['GET'])
def list_requests():
    return jsonify({'requests': _requests})


@app.route("/_set_action", methods=['POST'])
def set_action():
    global action_response
    action_response = request.get_json()

    return '', 204


@app.route("/1.0/action/<action>", methods=['POST'])
def action(action):
    return json.dumps(action_response), 200


if __name__ == "__main__":
    port = int(sys.argv[1])
    app.run(host='0.0.0.0', port=port, ssl_context=context, debug=True)
