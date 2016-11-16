# -*- coding: utf-8 -*-
# Copyright (C) 2016 Proformatique, Inc.
# SPDX-License-Identifier: GPL-3.0+

import sys

from flask import Flask, jsonify, request

app = Flask(__name__)

port = int(sys.argv[1])

invalid_credentials_uuid = '04b0087e-1661-4a42-8181-4b61e198204d'


@app.route('/1.0/users/<user_uuid>/presences', methods=['GET'])
def presences(user_uuid):
    xivo_uuid = request.args.get('xivo_uuid')
    if xivo_uuid == invalid_credentials_uuid:
        return '', 401
    elif user_uuid == 'unknown':
        return '', 404
    else:
        return jsonify({'user_uuid': user_uuid,
                        'xivo_uuid': xivo_uuid,
                        'presence': 'available'})


if __name__ == "__main__":
    context = ('/usr/local/share/ssl/ctid-ng/server.crt',
               '/usr/local/share/ssl/ctid-ng/server.key')
    app.run(host='0.0.0.0', port=port, ssl_context=context, debug=True)
