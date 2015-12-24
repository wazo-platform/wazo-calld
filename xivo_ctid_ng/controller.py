# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from threading import Thread
from xivo.auth_helpers import TokenRenewer
from xivo_auth_client import Client as AuthClient

from xivo_ctid_ng.core import plugin_manager
from xivo_ctid_ng.core.bus import CoreBus
from xivo_ctid_ng.core.ari_ import CoreARI
from xivo_ctid_ng.core.rest_api import api, CoreRestApi

logger = logging.getLogger(__name__)


class Controller(object):

    def __init__(self, config):
        auth_config = dict(config['auth'])
        auth_config.pop('key_file', None)
        auth_client = AuthClient(**auth_config)
        self.token_renewer = TokenRenewer(auth_client)
        self.bus = CoreBus(config)
        self.ari = CoreARI(config['ari'])
        self.rest_api = CoreRestApi(config)
        self._load_plugins(config)

    def run(self):
        logger.info('xivo-ctid-ng starting...')
        bus_thread = Thread(target=self.bus.run, name='bus_thread')
        bus_thread.start()
        ari_thread = Thread(target=self.ari.run, name='ari_thread')
        ari_thread.start()
        try:
            with self.token_renewer:
                self.rest_api.run()
        finally:
            logger.info('xivo-ctid-ng stopping...')
            self.bus.stop()
            self.ari.stop()
            bus_thread.join()
            ari_thread.join()

    def _load_plugins(self, global_config):
        load_args = [{
            'api': api,
            'ari': self.ari,
            'bus': self.bus,
            'config': global_config,
            'token_changed_subscribe': self.token_renewer.subscribe_to_token_change,
        }]
        plugin_manager.load_plugins(global_config['enabled_plugins'], load_args)
