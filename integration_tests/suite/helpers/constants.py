# Copyright 2015-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from kombu import Exchange
import os

ASSET_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', 'assets')

INVALID_ACL_TOKEN = 'invalid-acl-token'
VALID_TOKEN = 'valid-token'
VALID_TENANT = 'ffffffff-ffff-ffff-ffff-ffffffffffff'

BUS_EXCHANGE_XIVO = Exchange('xivo', type='topic')
BUS_EXCHANGE_COLLECTD = Exchange('collectd', type='topic', durable=False)
BUS_URL = 'amqp://guest:guest@localhost:5672//'
BUS_QUEUE_NAME = 'integration'

XIVO_UUID = '08c56466-8f29-45c7-9856-92bf1ba89b92'

SOME_CHANNEL_ID = '123456789.123'
SOME_CALL_ID = '987654321.123'
SOME_LINE_ID = 98343

ENDPOINT_AUTOANSWER = 'Test/integration-caller/autoanswer'
SOME_STASIS_APP = 'callcontrol'
SOME_STASIS_APP_INSTANCE = 'integration-tests'
