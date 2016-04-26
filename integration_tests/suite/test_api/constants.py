# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import os

ASSET_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', 'assets')
INVALID_ACL_TOKEN = 'invalid-acl-token'
VALID_TOKEN = 'valid-token'
BUS_EXCHANGE_NAME = 'xivo'
BUS_EXCHANGE_TYPE = 'topic'
BUS_URL = 'amqp://guest:guest@localhost:5672//'
BUS_QUEUE_NAME = 'integration'
XIVO_UUID = '08c56466-8f29-45c7-9856-92bf1ba89b92'
STASIS_APP_NAME = 'callcontrol'
STASIS_APP_INSTANCE_NAME = 'switchboard-red'
STASIS_APP_ARGS = [STASIS_APP_INSTANCE_NAME]
