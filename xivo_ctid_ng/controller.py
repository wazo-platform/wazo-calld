# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from threading import Thread
from xivo.token_renewer import TokenRenewer
from xivo_auth_client import Client as AuthClient

from xivo_ctid_ng.core import plugin_manager
from xivo_ctid_ng.core.bus import CoreBusConsumer
from xivo_ctid_ng.core.bus import CoreBusPublisher
from xivo_ctid_ng.core.collectd import CoreCollectd
from xivo_ctid_ng.core.ari_ import CoreARI
from xivo_ctid_ng.core.rest_api import api, CoreRestApi

logger = logging.getLogger(__name__)


class Controller(object):

    def __init__(self, config):
        auth_config = dict(config['auth'])
        auth_config.pop('key_file', None)
        auth_client = AuthClient(**auth_config)
        self.ari = CoreARI(config['ari'])
        self.bus_publisher = CoreBusPublisher(config)
        self.bus_consumer = CoreBusConsumer(config)
        self.collectd = CoreCollectd(config)
        self.rest_api = CoreRestApi(config)
        self.token_renewer = TokenRenewer(auth_client)
        self._load_plugins(config)

    def run(self):
        logger.info('xivo-ctid-ng starting...')
        bus_producer_thread = Thread(target=self.bus_publisher.run, name='bus_producer_thread')
        bus_producer_thread.start()
        collectd_thread = Thread(target=self.collectd.run, name='collectd_thread')
        collectd_thread.start()
        bus_consumer_thread = Thread(target=self.bus_consumer.run, name='bus_consumer_thread')
        bus_consumer_thread.start()
        ari_thread = Thread(target=self.ari.run, name='ari_thread')
        ari_thread.start()
        try:
            with self.token_renewer:
                self.rest_api.run()
        finally:
            logger.info('xivo-ctid-ng stopping...')
            self.ari.stop()
            self.bus_consumer.should_stop = True
            self.collectd.stop()
            self.bus_publisher.stop()
            ari_thread.join()
            bus_consumer_thread.join()
            collectd_thread.join()
            bus_producer_thread.join()

    def _load_plugins(self, global_config):
        load_args = [{
            'api': api,
            'ari': self.ari,
            'bus_publisher': self.bus_publisher,
            'bus_consumer': self.bus_consumer,
            'collectd': self.collectd,
            'config': global_config,
            'token_changed_subscribe': self.token_renewer.subscribe_to_token_change,
        }]
        plugin_manager.load_plugins(global_config['enabled_plugins'], load_args)
