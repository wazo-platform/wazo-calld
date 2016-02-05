# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import os
import yaml

ASSET_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', 'assets')
INVALID_ACL_TOKEN = 'invalid-acl-token'
VALID_TOKEN = 'valid-token'
BUS_EXCHANGE_NAME = 'xivo'
BUS_EXCHANGE_TYPE = 'topic'
BUS_URL = 'amqp://guest:guest@localhost:5672//'
BUS_QUEUE_NAME = 'integration'
XIVO_UUID = yaml.load(open(os.path.join(ASSET_ROOT, '_common', 'etc', 'xivo-ctid-ng', 'conf.d', 'uuid.yml'), 'r'))['uuid']
STASIS_APP_NAME = 'callcontrol'
STASIS_APP_INSTANCE_NAME = 'switchboard-red'
STASIS_APP_ARGS = [STASIS_APP_INSTANCE_NAME]
