# Copyright 2015-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import ari
import os
import logging
import tempfile

from ari.exceptions import ARINotFound
from ari.exceptions import ARINotInStasis
from contextlib import contextmanager
from requests.packages import urllib3
from xivo_test_helpers import until
from xivo_test_helpers.asset_launching_test_case import AssetLaunchingTestCase
from xivo_test_helpers.asset_launching_test_case import NoSuchService
from xivo_test_helpers.asset_launching_test_case import NoSuchPort

from .amid import AmidClient
from .ari_ import ARIClient
from .auth import AuthClient
from .bus import BusClient
from .chan_test import ChanTest
from .confd import ConfdClient
from .constants import ASSET_ROOT
from .ctid_ng import CtidNgClient
from .stasis import StasisClient
from .websocketd import WebsocketdClient
from .wait_strategy import CtidNgEverythingOkWaitStrategy

logger = logging.getLogger(__name__)

urllib3.disable_warnings()
if os.environ.get('TEST_LOGS') != 'verbose':
    logging.getLogger('swaggerpy.client').setLevel(logging.WARNING)
    logging.getLogger('amqp').setLevel(logging.INFO)


class WrongClient:
    def __init__(self, client_name):
        self.client_name = client_name

    def __getattr__(self, member):
        raise Exception('Could not create client {}'.format(self.client_name))


class IntegrationTest(AssetLaunchingTestCase):

    assets_root = ASSET_ROOT
    service = 'ctid-ng'
    wait_strategy = CtidNgEverythingOkWaitStrategy()

    @classmethod
    def _docker_compose_options(cls):
        return [
            '--file', os.path.join(cls.assets_root, 'docker-compose.yml'),
            '--file', os.path.join(cls.assets_root, 'docker-compose.{}.override.yml'.format(cls.asset)),
            '--project-name', cls.service,
        ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            cls.reset_clients()
            cls.reset_bus_client()
            cls.wait_strategy.wait(cls)
        except Exception:
            with tempfile.NamedTemporaryFile(delete=False) as logfile:
                logfile.write(cls.log_containers())
                logger.debug('Container logs dumped to %s', logfile.name)
            cls.tearDownClass()
            raise

    @classmethod
    def reset_clients(cls):
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
            cls.confd = ConfdClient('localhost', cls.service_port(9486, 'confd'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.confd = WrongClient('confd')
        try:
            cls.ctid_ng = CtidNgClient('localhost', cls.service_port(9500, 'ctid-ng'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.ctid_ng = WrongClient('ctid_ng')
        try:
            cls.stasis = StasisClient('localhost', cls.service_port(5039, 'ari'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.stasis = WrongClient('stasis')
        try:
            cls.websocketd = WebsocketdClient('localhost', cls.service_port(9502, 'websocketd'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.websocketd = WrongClient('websocketd')

    @classmethod
    def reset_bus_client(cls):
        '''
        The bus client is "special" because it has state: when calling
        listen_events(), it stores events in its members. If reset like the
        others, we lose this state.

        '''
        try:
            cls.bus = BusClient.from_connection_fields(host='localhost', port=cls.service_port(5672, 'rabbitmq'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.bus = WrongClient('bus')

    @classmethod
    @contextmanager
    def _ctid_ng_stopped(cls):
        cls._stop_ctid_ng()
        yield
        cls._start_ctid_ng()

    @classmethod
    def _restart_ctid_ng(cls):
        cls._stop_ctid_ng()
        cls._start_ctid_ng()

    @classmethod
    def _stop_ctid_ng(cls):
        cls.stop_service('ctid-ng')

    @classmethod
    def _start_ctid_ng(cls):
        cls.start_service('ctid-ng')
        cls.reset_clients()
        until.true(cls.ctid_ng.is_up, tries=5)

    @classmethod
    @contextmanager
    def confd_stopped(cls):
        cls.stop_service('confd')
        yield
        cls.start_service('confd')
        cls.reset_clients()
        until.true(cls.confd.is_up, tries=5)


class RealAsteriskIntegrationTest(IntegrationTest):
    asset = 'real_asterisk'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.chan_test = ChanTest(cls.ari_config())

    @classmethod
    def ari_config(cls):
        return {
            'base_url': 'http://localhost:{port}'.format(port=cls.service_port(5039, 'ari')),
            'username': 'xivo',
            'password': 'xivo',
        }

    def setUp(self):
        super().setUp()
        self.ari = ari.connect(**self.ari_config())
        self.reset_ari()

    def tearDown(self):
        super().tearDown()

    def reset_ari(self):
        for channel in self.ari.channels.list():
            try:
                channel.hangup()
            except (ARINotInStasis, ARINotFound):
                pass

        for bridge in self.ari.bridges.list():
            try:
                bridge.destroy()
            except (ARINotInStasis, ARINotFound):
                pass
