# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import sys

from flask import Flask, jsonify, request

app = Flask(__name__)

port = int(sys.argv[1])

context = ('/usr/local/share/ssl/auth/server.crt', '/usr/local/share/ssl/auth/server.key')

valid_tokens = {'valid-token': 'uuid'}
wrong_acl_tokens = {'invalid-acl-token'}


@app.route("/_set_token", methods=['POST'])
def add_token():
    request_body = request.get_json()
    token = request_body['token']
    auth_id = request_body['auth_id']

    valid_tokens[token] = auth_id

    return '', 204


@app.route("/0.1/token/<token>", methods=['HEAD'])
def token_head_ok(token):
    if token in wrong_acl_tokens:
        return '', 403
    elif token in valid_tokens:
        return '', 204
    else:
        return '', 401


@app.route("/0.1/token/<token>", methods=['GET'])
def token_get(token):
    if token not in valid_tokens:
        return '', 404

    return jsonify({
        'data': {
            'auth_id': valid_tokens[token],
            'token': token,
            'xivo_user_uuid': valid_tokens[token]
        }
    })


@app.route("/0.1/token", methods=['POST'])
def token_post():
    return jsonify({
        'data': {
            'auth_id': valid_tokens['valid-token'],
            'token': 'valid-token',
        }
    })


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, ssl_context=context, debug=True)
