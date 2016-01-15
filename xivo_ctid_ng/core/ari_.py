# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import ari
import errno
import logging
import requests
import socket
import time

from requests.exceptions import HTTPError
from websocket import WebSocketException

from .exceptions import ARIUnreachable

logger = logging.getLogger(__name__)

APPLICATION_NAME = 'callcontrol'


class CoreARI(object):

    def __init__(self, config):
        self.config = config
        self._should_reconnect = True
        try:
            self.client = ari.connect(**config['connection'])
        except requests.ConnectionError:
            logger.critical('ARI config: %s', config['connection'])
            raise ARIUnreachable()

    def run(self):
        logger.debug('ARI client listening...')
        while True:
            try:
                self.client.run(apps=[APPLICATION_NAME])
            except socket.error as e:
                if e.errno == errno.EPIPE:
                    # bug in ari-py when calling client.close(): ignore it and stop
                    logger.error('Error while listening for ARI events: %s', e)
                    return
                else:
                    error = e
            except (WebSocketException, HTTPError) as e:
                error = e

            logger.warning('ARI connection error: %s...', error)

            if not self._should_reconnect:
                return

            delay = self.config['reconnection_delay']
            logger.warning('Reconnecting to ARI in %s seconds', delay)
            time.sleep(delay)

    def stop(self):
        try:
            self._should_reconnect = False
            self.client.close()
        except RuntimeError:
            pass  # bug in ari-py when calling client.close()
