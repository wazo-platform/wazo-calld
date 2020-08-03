# Copyright 2015-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

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
from .constants import ASSET_ROOT, VALID_TOKEN
from .calld import LegacyCalldClient, CalldClient
from .phoned import PhonedClient
from .stasis import StasisClient
from .wait_strategy import CalldEverythingOkWaitStrategy

logger = logging.getLogger(__name__)

urllib3.disable_warnings()
if os.environ.get('TEST_LOGS') != 'verbose':
    logging.getLogger('swaggerpy.client').setLevel(logging.WARNING)


class ClientCreateException(Exception):

    def __init__(self, client_name):
        super().__init__(f'Could not create client {client_name}')


class WrongClient:
    def __init__(self, client_name):
        self.client_name = client_name

    def __getattr__(self, member):
        raise ClientCreateException(self.client_name)


class IntegrationTest(AssetLaunchingTestCase):

    assets_root = ASSET_ROOT
    service = 'calld'
    wait_strategy = CalldEverythingOkWaitStrategy()

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
            cls.calld = LegacyCalldClient('localhost', cls.service_port(9500, 'calld'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.calld = WrongClient('calld')
        try:
            cls.calld_client = cls.make_calld(token=VALID_TOKEN)
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.calld_client = WrongClient('calld-client')
        try:
            cls.phoned = PhonedClient('localhost', cls.service_port(9498, 'phoned'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.phoned = WrongClient('phoned')
        try:
            cls.stasis = StasisClient('localhost', cls.service_port(5039, 'ari'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.stasis = WrongClient('stasis')

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
    def make_calld(cls, token=VALID_TOKEN):
        return CalldClient('localhost', cls.service_port(9500, 'calld'), prefix=None, https=False, token=token)

    @classmethod
    @contextmanager
    def _calld_stopped(cls):
        cls._stop_calld()
        yield
        cls._start_calld()

    @classmethod
    def _restart_calld(cls):
        cls._stop_calld()
        cls._start_calld()

    @classmethod
    def _stop_calld(cls):
        cls.stop_service('calld')

    @classmethod
    def _start_calld(cls):
        cls.start_service('calld')
        cls.reset_clients()
        until.true(cls.calld_client.is_up, tries=5)

    @classmethod
    @contextmanager
    def confd_stopped(cls):
        cls.stop_service('confd')
        try:
            yield
        finally:
            cls.start_service('confd')
            cls.reset_clients()
            until.true(cls.confd.is_up, tries=5)

    @classmethod
    @contextmanager
    def amid_stopped(cls):
        cls.stop_service('amid')
        try:
            yield
        finally:
            cls.start_service('amid')
            cls.reset_clients()
            until.true(cls.amid.is_up, tries=5)

    @classmethod
    @contextmanager
    def ari_stopped(cls):
        cls.stop_service('ari')
        try:
            yield
        finally:
            cls.start_service('ari')

            def ari_is_up():
                return ARIClient('localhost', cls.service_port(5039, 'ari'))

            until.return_(ari_is_up, timeout=5, message='ari did not restart')
            cls.reset_clients()

    def setUp(self):
        super().setUp()
        try:
            self.calld_client.set_token(VALID_TOKEN)
        except ClientCreateException:
            pass


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
