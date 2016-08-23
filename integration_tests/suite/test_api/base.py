# -*- coding: utf-8 -*-
# Copyright 2015-2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging
import time

from requests.packages import urllib3
from xivo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase
from xivo_test_helpers.asset_launching_test_case import NoSuchService
from xivo_test_helpers.asset_launching_test_case import NoSuchPort

from .amid import AmidClient
from .ari_ import ARIClient
from .auth import AuthClient
from .bus import BusClient
from .confd import ConfdClient
from .constants import ASSET_ROOT
from .ctid_ng import CtidNgClient
from .stasis import StasisClient
from .wait_strategy import CtidNgConnectionsOkWaitStrategy

logger = logging.getLogger(__name__)

urllib3.disable_warnings()


class WrongClient(object):
    def __init__(self, client_name):
        self.client_name = client_name

    def __getattr__(self, member):
        raise Exception('Could not create client {}'.format(self.client_name))


class IntegrationTest(AssetLaunchingTestCase):

    assets_root = ASSET_ROOT
    service = 'ctid-ng'
    wait_strategy = CtidNgConnectionsOkWaitStrategy()

    @classmethod
    def setUpClass(cls):
        super(IntegrationTest, cls).setUpClass()
        try:
            cls.amid = AmidClient('localhost', cls.service_port(9491, 'amid'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.amid = WrongClient('amid')
        try:
            cls.ari = ARIClient('localhost', cls.service_port(5039, 'ari'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.ari = WrongClient('ari')
        try:
            cls.auth = AuthClient('localhost', cls.service_port(9497, 'auth'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.auth = WrongClient('auth')
        try:
            cls.bus = BusClient('localhost', cls.service_port(5672, 'rabbitmq'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.bus = WrongClient('bus')
        try:
            cls.confd = ConfdClient('localhost', cls.service_port(9486, 'confd'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.confd = WrongClient('confd')
        cls.ctid_ng = CtidNgClient()
        cls.stasis = StasisClient()
        cls.wait_strategy.wait(cls)

    @classmethod
    def wait_for_ctid_ng_to_connect_to_bus(cls):
        time.sleep(4)
