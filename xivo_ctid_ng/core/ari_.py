# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

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
