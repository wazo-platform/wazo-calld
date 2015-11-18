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
from flask import request

logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)

port = int(sys.argv[1])

context = ('/usr/local/share/ssl/confd/server.crt', '/usr/local/share/ssl/confd/server.key')

_requests = []
_responses = {
    'users': {}
}


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


@app.route('/_set_response', methods=['POST'])
def set_response():
    global _responses
    request_body = json.loads(request.data)
    set_response = request_body['response']
    set_response_body = request_body['content']
    _responses[set_response] = set_response_body
    return '', 204


@app.route('/users/<int:user_id>')
def user(user_id):
    if user_id not in _responses['users']:
        return '', 404
    return jsonify(_responses['users'][user_id])


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, ssl_context=context, debug=True)
