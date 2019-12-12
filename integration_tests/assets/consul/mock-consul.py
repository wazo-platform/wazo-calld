# -*- coding: utf-8 -*-
# Copyright 2016-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import sys

from flask import Flask, jsonify, request

app = Flask(__name__)

port = int(sys.argv[1])


def default_auth(xivo_uuid):
    return {'Service': 'wazo-auth',
            'Address': 'auth',
            'Port': 9497,
            'Tags': [xivo_uuid, 'wazo-auth']}


def default_calld(xivo_uuid):
    return {'Service': 'wazo-calld',
            'Address': 'remote_calld',
            'Port': 9501,
            'Tags': [xivo_uuid, 'wazo-calld']}


services = {
    'wazo-auth': {
        '51400e55-2dc3-4cfc-a2f2-a4d4f0f8b217': default_auth('51400e55-2dc3-4cfc-a2f2-a4d4f0f8b217'),
        '196e42b9-bbfe-4c03-b3d4-684dffd01603': default_auth('196e42b9-bbfe-4c03-b3d4-684dffd01603'),
        '04b0087e-1661-4a42-8181-4b61e198204d': default_auth('04b0087e-1661-4a42-8181-4b61e198204d'),
        '5720ee16-61cc-412e-93c9-ae06fa0be845': default_auth('5720ee16-61cc-412e-93c9-ae06fa0be845'),
    },
    'wazo-calld': {
        '04b0087e-1661-4a42-8181-4b61e198204d': default_calld('04b0087e-1661-4a42-8181-4b61e198204d'),
        '5720ee16-61cc-412e-93c9-ae06fa0be845': default_calld('5720ee16-61cc-412e-93c9-ae06fa0be845'),
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
    app.run(host='0.0.0.0', port=port, debug=True)
