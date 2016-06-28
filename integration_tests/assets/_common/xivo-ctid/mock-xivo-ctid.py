# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import sys

from flask import Flask, jsonify, request

app = Flask(__name__)

port = int(sys.argv[1])

valid_uuid = {'valid-uuid': 'my-user-uuid'}


@app.route("/0.1/users/<user_uuid>", methods=['GET'])
def get_presence(user_uuid):
    if user_uuid not in valid_uuid['valid-uuid']:
        return '', 404

    return jsonify({
        'id': 1,
        'user_uuid': valid_uuid['valid-uuid'],
        'origin_uuid': '08c56466-8f29-45c7-9856-92bf1ba89b92',
        'presence': 'available'
    })


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=True)
