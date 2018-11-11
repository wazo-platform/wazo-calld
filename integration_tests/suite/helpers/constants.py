# Copyright 2015-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from kombu import Exchange
import os

ASSET_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', 'assets')
INVALID_ACL_TOKEN = 'invalid-acl-token'
VALID_TOKEN = 'valid-token'
BUS_EXCHANGE_XIVO = Exchange('xivo', type='topic')
BUS_EXCHANGE_COLLECTD = Exchange('collectd', type='topic', durable=False)
BUS_URL = 'amqp://guest:guest@localhost:5672//'
BUS_QUEUE_NAME = 'integration'
XIVO_UUID = '08c56466-8f29-45c7-9856-92bf1ba89b92'
STASIS_APP_NAME = 'callcontrol'
STASIS_APP_INSTANCE_NAME = 'switchboard-red'
STASIS_APP_ARGS = [STASIS_APP_INSTANCE_NAME]
DB_URI = 'postgres://{DB_USER}:{DB_PASSWORD}@{HOST}:{PORT}/{DB_NAME}'.format(
    DB_USER='postgres',
    DB_PASSWORD='mysecretpassword',
    HOST='localhost',
    PORT='{PORT}',
    DB_NAME='mongooseim'
)
MONGOOSEIM_ODBC_START_INTERVAL = 1
