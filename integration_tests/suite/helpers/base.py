# Copyright 2015-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import os
import tempfile
import uuid
from contextlib import contextmanager

import urllib3
from wazo_test_helpers import until
from wazo_test_helpers.asset_launching_test_case import (
    AssetLaunchingTestCase,
    NoSuchPort,
    NoSuchService,
)
from wazo_test_helpers.auth import AuthClient, MockCredentials, MockUserToken

from .amid import MockAmidClient
from .ari_ import ARIClient
from .bus import BusClient
from .calld import CalldClient, LegacyCalldClient
from .confd import ConfdClient
from .constants import (
    ASSET_ROOT,
    CALLD_SERVICE_TENANT,
    CALLD_SERVICE_TOKEN,
    CALLD_SERVICE_USER_UUID,
    VALID_TENANT,
    VALID_TOKEN,
)
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
            cls.setup_tokens()
            cls.wait_strategy.wait(cls)
        except Exception:
            with tempfile.NamedTemporaryFile(delete=False) as logfile:
                logfile.write(cls.log_containers())
                logger.debug('Container logs dumped to %s', logfile.name)
            cls.tearDownClass()
            raise

    @classmethod
    def setup_tokens(cls):
        token = MockUserToken(
            str(CALLD_SERVICE_TOKEN),
            str(CALLD_SERVICE_USER_UUID),
            metadata={
                'uuid': str(CALLD_SERVICE_TOKEN),
                'tenant_uuid': str(CALLD_SERVICE_TENANT),
            },
        )
        cls.auth.set_token(token)
        credential = MockCredentials('wazo-calld-service', 'opensesame')
        cls.auth.set_valid_credentials(credential, str(CALLD_SERVICE_TOKEN))
        cls.auth.set_tenants(
            {
                'uuid': str(CALLD_SERVICE_TENANT),
                'name': 'wazo-calld-service-tenant',
                'parent_uuid': str(CALLD_SERVICE_TENANT),
            },
            {
                'uuid': str(VALID_TENANT),
                'name': 'valid-tenant',
                'parent_uuid': str(CALLD_SERVICE_TENANT),
            },
        )

    @classmethod
    def reset_clients(cls):
        try:
            cls.amid = cls.make_amid()
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.amid = WrongClient('amid')
        try:
            cls.ari = ARIClient('127.0.0.1', cls.service_port(5039, 'ari'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.ari = WrongClient('ari')
        try:
            cls.auth = AuthClient('127.0.0.1', cls.service_port(9497, 'auth'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.auth = WrongClient('auth')
        try:
            cls.confd = ConfdClient('127.0.0.1', cls.service_port(9486, 'confd'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.confd = WrongClient('confd')
        try:
            cls.calld = LegacyCalldClient('127.0.0.1', cls.service_port(9500, 'calld'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.calld = WrongClient('calld')
        try:
            cls.calld_client = cls.make_calld(token=VALID_TOKEN)
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.calld_client = WrongClient('calld-client')
        try:
            cls.phoned = PhonedClient('127.0.0.1', cls.service_port(9498, 'phoned'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.phoned = WrongClient('phoned')
        try:
            cls.stasis = StasisClient('127.0.0.1', cls.service_port(5672, 'rabbitmq'))
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
            cls.bus = BusClient.from_connection_fields(
                host='127.0.0.1',
                port=cls.service_port(5672, 'rabbitmq'),
                exchange_name='wazo-headers',
                exchange_type='headers',
            )
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.bus = WrongClient('bus')

    @classmethod
    def reset_ari_bus(cls):
        try:
            cls.stasis = StasisClient('127.0.0.1', cls.service_port(5672, 'rabbitmq'))
        except (NoSuchService, NoSuchPort) as e:
            logger.debug(e)
            cls.stasis = WrongClient('stasis')

    @classmethod
    def make_amid(cls):
        return MockAmidClient('127.0.0.1', cls.service_port(9491, 'amid'))

    @classmethod
    def make_calld(cls, token=VALID_TOKEN):
        return CalldClient(
            '127.0.0.1',
            cls.service_port(9500, 'calld'),
            prefix=None,
            https=False,
            token=token,
        )

    @classmethod
    def make_user_calld(cls, user_uuid, tenant_uuid=None):
        token_id = str(uuid.uuid4())
        tenant_uuid = tenant_uuid or str(uuid.uuid4())
        cls.auth.set_token(
            MockUserToken(
                token_id, metadata={'tenant_uuid': tenant_uuid}, user_uuid=user_uuid
            )
        )
        return cls.make_calld(token=token_id)

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
        until.true(cls.calld_client.is_up, tries=10)

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
            cls.reset_clients()
            until.true(cls.ari.is_up, tries=5)

    def setUp(self):
        super().setUp()
        try:
            self.calld_client.set_token(VALID_TOKEN)
        except ClientCreateException:
            pass


def make_user_uuid():
    return str(uuid.uuid4())
