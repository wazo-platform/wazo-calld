# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo import auth_verifier

logger = logging.getLogger(__name__)

required_acl = auth_verifier.required_acl
