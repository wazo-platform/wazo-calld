# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
import sys

from flask import Flask
from flask import jsonify
from flask import make_response

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)


@app.route('/ari/api-docs/<path:file_name>')
def swagger(file_name):
    with open('/usr/local/share/ari/api-docs/{file_name}'.format(file_name=file_name), 'r') as swagger_file:
        swagger_spec = swagger_file.read()
        swagger_spec = swagger_spec.replace('localhost:8088', 'ari:{port}'.format(port=port))
        return make_response(swagger_spec, 200, {'Content-Type': 'application/json'})


@app.route('/ari/<path:path>', methods=['GET', 'PUT', 'POST', 'DELETE'])
def fail():
    return jsonify('', 500)


if __name__ == '__main__':
    port = int(sys.argv[1])
    app.run(host='0.0.0.0', port=port, debug=True)
    # context = ('/usr/local/share/ssl/ari/server.crt', '/usr/local/share/ssl/ari/server.key')
    # app.run(host='0.0.0.0', port=port, ssl_context=context, debug=True)
