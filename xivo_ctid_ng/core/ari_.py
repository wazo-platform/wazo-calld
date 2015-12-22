# -*- coding: utf-8 -*-
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

import ari
import logging
import requests
import socket

from .exceptions import ARIUnreachable

logger = logging.getLogger(__name__)

APPLICATION_NAME = 'callcontrol'


class CoreARI(object):

    def __init__(self, config):
        try:
            self.client = ari.connect(**config['connection'])
        except requests.ConnectionError:
            logger.critical('ARI config: %s', config['connection'])
            raise ARIUnreachable()

    def run(self):
        try:
            self.client.run(apps=[APPLICATION_NAME])
        except socket.error as e:
            logger.error('Error while listening for ARI events: %s', e)  # bug in ari-py when calling client.close()

    def stop(self):
        try:
            self.client.close()
        except RuntimeError:
            pass  # bug in ari-py when calling client.close()
