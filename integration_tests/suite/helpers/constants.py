# Copyright 2015-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from kombu import Exchange

ASSET_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', 'assets')

INVALID_ACL_TOKEN = 'invalid-acl-token'
VALID_TENANT = 'ffffffff-ffff-ffff-ffff-ffffffffffff'
VALID_TENANT_MULTITENANT_1 = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee2'
VALID_TENANT_MULTITENANT_2 = 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeee3'
VALID_TOKEN = 'valid-token'
VALID_TOKEN_MULTITENANT = 'valid-token-multitenant'

CALLD_SERVICE_TOKEN = 'wazo-calld-service-token'
CALLD_SERVICE_TENANT = '61b625fa-82d0-44df-8134-f07792e67401'
CALLD_SERVICE_USER_UUID = '0dd433d9-545c-493b-9875-0fe7758a81fb'

AMID_SERVICE_TOKEN = 'wazo-amid-service-token'
AMID_SERVICE_USER_UUID = '0dd433d9-545c-493b-9875-000000000000'

BUS_EXCHANGE_WAZO = Exchange('wazo-headers', type='headers')
BUS_EXCHANGE_COLLECTD = Exchange('collectd', type='topic', durable=False)
BUS_QUEUE_NAME = 'integration'

XIVO_UUID = '08c56466-8f29-45c7-9856-92bf1ba89b92'

SOME_CHANNEL_ID = '123456789.123'
SOME_CALL_ID = '987654321.123'
SOME_LINE_ID = 98343

ENDPOINT_AUTOANSWER = 'Test/integration-caller/autoanswer'
SOME_STASIS_APP = 'callcontrol'
SOME_STASIS_APP_INSTANCE = 'integration-tests'
