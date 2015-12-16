# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from threading import Thread
from xivo_ctid_ng.core.rest_api import app
from xivo_ctid_ng.core.rest_api import CoreRestApi
from xivo_ctid_ng.core.bus import CoreBus

logger = logging.getLogger(__name__)


class Controller(object):
    def __init__(self, config):
        app.config['ari'] = config['ari']
        app.config['confd'] = config['confd']
        app.config['auth'] = config['auth']
        self.rest_api = CoreRestApi(config)
        self.bus = CoreBus(config['bus'])

    def run(self):
        logger.info('xivo-ctid-ng starting...')
        bus_thread = Thread(target=self.bus.run, name='bus_thread')
        bus_thread.start()
        try:
            self.rest_api.run()
        finally:
            logger.info('xivo-ctid-ng stopping...')
            self.bus.should_stop = True
            bus_thread.join()
