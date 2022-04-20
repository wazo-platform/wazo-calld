# Copyright 2015-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from threading import Thread
from functools import partial
from wazo_auth_client import Client as AuthClient
from xivo import plugin_helpers
from xivo import pubsub
from xivo.config_helper import get_xivo_uuid
from xivo.consul_helpers import ServiceCatalogRegistration
from xivo.status import StatusAggregator, TokenStatus
from xivo.token_renewer import TokenRenewer

from .ari_ import CoreARI
from .asyncio_ import CoreAsyncio
from .auth import init_master_tenant
from .bus import CoreBusConsumer, CoreBusPublisher
from .collectd import CoreCollectd
from .http_server import api, HTTPServer
from .service_discovery import self_check

logger = logging.getLogger(__name__)


class Controller:

    def __init__(self, config):
        xivo_uuid = get_xivo_uuid(logger)
        auth_client = AuthClient(**config['auth'])
        self.asyncio = CoreAsyncio()
        self.bus_consumer = CoreBusConsumer(**config['bus'])
        self.ari = CoreARI(config['ari'], self.bus_consumer)
        self.bus_publisher = CoreBusPublisher(service_uuid=config['uuid'], **config['bus'])
        self.collectd = CoreCollectd(config)
        self.http_server = HTTPServer(config)
        self.status_aggregator = StatusAggregator()
        self.token_renewer = TokenRenewer(auth_client)
        self.token_status = TokenStatus()
        self._service_registration_params = ['wazo-calld',
                                             xivo_uuid,
                                             config['consul'],
                                             config['service_discovery'],
                                             config['bus'],
                                             partial(self_check, config)]

        self._pubsub = pubsub.Pubsub()
        plugin_helpers.load(
            namespace='wazo_calld.plugins',
            names=config['enabled_plugins'],
            dependencies={
                'api': api,
                'ari': self.ari,
                'asyncio': self.asyncio,
                'bus_publisher': self.bus_publisher,
                'bus_consumer': self.bus_consumer,
                'collectd': self.collectd,
                'config': config,
                'status_aggregator': self.status_aggregator,
                'pubsub': self._pubsub,
                'token_changed_subscribe': self.token_renewer.subscribe_to_token_change,
                'next_token_changed_subscribe': self.token_renewer.subscribe_to_next_token_change,
            }
        )

        if not config['auth'].get('master_tenant_uuid'):
            self.token_renewer.subscribe_to_next_token_details_change(
                init_master_tenant
            )

    def run(self):
        logger.info('wazo-calld starting...')
        self.token_renewer.subscribe_to_token_change(self.token_status.token_change_callback)
        self.status_aggregator.add_provider(self.ari.provide_status)
        self.status_aggregator.add_provider(self.bus_consumer.provide_status)
        self.status_aggregator.add_provider(self.token_status.provide_status)
        self.ari.init_client()
        collectd_thread = Thread(target=self.collectd.run, name='collectd_thread')
        collectd_thread.start()
        asyncio_thread = Thread(target=self.asyncio.run, name='asyncio_thread')
        asyncio_thread.start()
        try:
            with self.token_renewer:
                with self.bus_consumer:
                    with ServiceCatalogRegistration(*self._service_registration_params):
                        self.http_server.run()
        finally:
            logger.info('wazo-calld stopping...')
            self._pubsub.publish('stopping', None)
            self.asyncio.stop()
            self.collectd.stop()
            logger.debug('joining asyncio thread')
            asyncio_thread.join()
            logger.debug('joining collectd thread')
            collectd_thread.join()
            logger.debug('done joining')

    def stop(self, reason):
        logger.warning('Stopping wazo-calld: %s', reason)
        self.http_server.stop()
