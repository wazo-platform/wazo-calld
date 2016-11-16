# -*- coding: utf-8 -*-
# Copyright (C) 2016 Proformatique, Inc.
# SPDX-License-Identifier: GPL-3.0+

import sys

from flask import Flask, jsonify, request

app = Flask(__name__)

port = int(sys.argv[1])


def default_auth(xivo_uuid):
    return {'Service': 'xivo-auth',
            'Address': 'auth',
            'Port': 9497,
            'Tags': [xivo_uuid, 'xivo-auth']}


def default_ctid_ng(xivo_uuid):
    return {'Service': 'xivo-ctid-ng',
            'Address': 'remote_ctid_ng',
            'Port': 9501,
            'Tags': [xivo_uuid, 'xivo-ctid-ng']}

services = {
    'xivo-auth': {
        '51400e55-2dc3-4cfc-a2f2-a4d4f0f8b217': default_auth('51400e55-2dc3-4cfc-a2f2-a4d4f0f8b217'),
        '196e42b9-bbfe-4c03-b3d4-684dffd01603': default_auth('196e42b9-bbfe-4c03-b3d4-684dffd01603'),
        '04b0087e-1661-4a42-8181-4b61e198204d': default_auth('04b0087e-1661-4a42-8181-4b61e198204d'),
        '5720ee16-61cc-412e-93c9-ae06fa0be845': default_auth('5720ee16-61cc-412e-93c9-ae06fa0be845'),
    },
    'xivo-ctid-ng': {
        '04b0087e-1661-4a42-8181-4b61e198204d': default_ctid_ng('04b0087e-1661-4a42-8181-4b61e198204d'),
        '5720ee16-61cc-412e-93c9-ae06fa0be845': default_ctid_ng('5720ee16-61cc-412e-93c9-ae06fa0be845'),
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
