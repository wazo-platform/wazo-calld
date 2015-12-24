# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from requests.packages import urllib3
from xivo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase

from .constants import ASSET_ROOT
from .ctid_ng import CtidNgClient
from .ari import ARIClient
from .bus import BusClient
from .confd import ConfdClient
from .stasis import StasisClient

logger = logging.getLogger(__name__)

urllib3.disable_warnings()


class IntegrationTest(AssetLaunchingTestCase):

    assets_root = ASSET_ROOT
    service = 'ctid-ng'

    def __init__(self, *args, **kwargs):
        super(IntegrationTest, self).__init__(*args, **kwargs)
        self.ctid_ng = CtidNgClient()
        self.ari = ARIClient()
        self.bus = BusClient()
        self.confd = ConfdClient()
        self.stasis = StasisClient()
