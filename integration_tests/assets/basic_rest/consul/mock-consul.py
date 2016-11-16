# -*- coding: utf-8 -*-
# Copyright (C) 2016 Proformatique, Inc.
# SPDX-License-Identifier: GPL-3.0+

import sys

from flask import Flask, jsonify, request

app = Flask(__name__)

port = int(sys.argv[1])

services = {
    'xivo-auth': {
        '51400e55-2dc3-4cfc-a2f2-a4d4f0f8b217': {
            'Service': 'xivo-auth',
            'Address': 'auth',
            'Port': 9497,
            'Tags': ['51400e55-2dc3-4cfc-a2f2-a4d4f0f8b217', 'xivo-auth'],
        },
    },
}


@app.route('/v1/catalog/datacenters', methods=['GET'])
def datacenters():
    return jsonify(['dc1'])


@app.route('/v1/health/service/<service_name>', methods=['GET'])
def service(service_name):
    uuid = request.args.get('tag')
    service_configs = services.get(service_name)
    if not service_configs:
        return jsonify([])
    service_config = service_configs.get(uuid)
    if not service_config:
        return jsonify([])
    return jsonify([{'Service': service_config}])


if __name__ == "__main__":
    context = ('/usr/local/share/ssl/consul/server.crt',
               '/usr/local/share/ssl/consul/server.key')
    app.run(host='0.0.0.0', port=port, ssl_context=context, debug=True)
