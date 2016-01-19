# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo import rest_api_helpers

logger = logging.getLogger(__name__)


APIException = rest_api_helpers.APIException


class ARIUnreachable(Exception):

    def __init__(self):
        super(ARIUnreachable, self).__init__('ARI server unreachable... stopping')
