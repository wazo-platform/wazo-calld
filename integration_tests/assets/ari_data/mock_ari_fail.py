#!/usr/bin/env python3
# Copyright 2015-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
import sys

from flask import Flask, Response, jsonify, make_response

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('wazo-ari-mock')


@app.errorhandler(500)
def handle_generic(e: Exception) -> Response:
    logger.error(f'Exception: {e}')
    return jsonify({'error': str(e)})


@app.route('/ari/api-docs/<path:file_name>')
def swagger(file_name: str) -> Response:
    with open(f'/usr/local/share/ari/api-docs/{file_name}') as swagger_file:
        swagger_spec = swagger_file.read()
        swagger_spec = swagger_spec.replace('localhost:8088', f'ari:{port}')
        return make_response(swagger_spec, 200, {'Content-Type': 'application/json'})


@app.route('/ari/<path:path>', methods=['GET', 'PUT', 'POST', 'DELETE'])
def fail(path: str) -> tuple[str, int]:
    return '', 500


if __name__ == '__main__':
    port = int(sys.argv[1])
    app.run(host='0.0.0.0', port=port, debug=True)
