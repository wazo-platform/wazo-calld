# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from threading import Thread
from xivo.auth_helpers import TokenRenewer
from xivo_auth_client import Client as AuthClient

from xivo_ctid_ng.core.rest_api import CoreRestApi
from xivo_ctid_ng.core.bus import CoreBus

logger = logging.getLogger(__name__)


class Controller(object):

    def __init__(self, config):
        auth_config = dict(config['auth'])
        auth_config.pop('key_file', None)
        auth_client = AuthClient(**auth_config)
        self.token_renewer = TokenRenewer(auth_client)
        self.rest_api = CoreRestApi(config, self.token_renewer.subscribe_to_token_change)
        self.bus = CoreBus(config['bus'])

    def run(self):
        logger.info('xivo-ctid-ng starting...')
        bus_thread = Thread(target=self.bus.run, name='bus_thread')
        bus_thread.start()
        try:
            with self.token_renewer:
                self.rest_api.run()
        finally:
            logger.info('xivo-ctid-ng stopping...')
            self.bus.should_stop = True
            bus_thread.join()
