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
from flask import make_response
from flask import request

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
