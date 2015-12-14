# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 Avencall
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

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
