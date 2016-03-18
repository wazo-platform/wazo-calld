# -*- coding: utf-8 -*-
# Copyright 2015-2016 by Avencall
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


def not_found(error):
    return error.response is not None and error.response.status_code == 404


class CoreARI(object):

    def __init__(self, config):
        self.config = config
        self._running = False
        self._should_reconnect = True
        try:
            self.client = ari.connect(**config['connection'])
        except requests.ConnectionError:
            logger.critical('ARI config: %s', config['connection'])
            raise ARIUnreachable()

    def run(self):
        logger.debug('ARI client listening...')
        while True:
            self._running = True
            try:
                self.client.run(apps=[APPLICATION_NAME])
            except socket.error as e:
                if e.errno == errno.EPIPE:
                    # bug in ari-py when calling client.close(): ignore it and stop
                    logger.error('Error while listening for ARI events: %s', e)
                    self._running = False
                    return
                else:
                    error = e
            except (WebSocketException, HTTPError) as e:
                error = e
            finally:
                self._running = False

            logger.warning('ARI connection error: %s...', error)

            if not self._should_reconnect:
                return

            delay = self.config['reconnection_delay']
            logger.warning('Reconnecting to ARI in %s seconds', delay)
            time.sleep(delay)

    def _sync(self):
        '''self.sync() should be called before calling self.stop(), in case the
        ari client does not have the websocket yet'''

        while self._running and not self.client.websockets:
            time.sleep(0.1)

    def stop(self):
        try:
            self._should_reconnect = False
            self._sync()
            self.client.close()
        except RuntimeError:
            pass  # bug in ari-py when calling client.close()
