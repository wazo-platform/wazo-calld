# -*- coding: utf-8 -*-
# Copyright 2015-2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import ari
import errno
import logging
import requests
import socket
import time

from contextlib import contextmanager
from requests.exceptions import HTTPError
from websocket import WebSocketException

from .exceptions import ARIUnreachable

logger = logging.getLogger(__name__)

APPLICATION_NAME = 'callcontrol'


def not_found(error):
    return error.response is not None and error.response.status_code == 404


def service_unavailable(error):
    return error.response is not None and error.response.status_code == 503


def asterisk_is_loading(error):
    return not_found(error) or service_unavailable(error)


class CoreARI(object):

    def __init__(self, config):
        self.config = config
        self._is_running = False
        self._should_reconnect = True
        self.client = self._new_ari_client(config['connection'],
                                           config['startup_connection_tries'],
                                           config['startup_connection_delay'])

    def _new_ari_client(self, ari_config, connection_tries, connection_delay):
        for _ in xrange(connection_tries):
            try:
                return ari.connect(**ari_config)
            except requests.ConnectionError:
                logger.critical('ARI config: %s', ari_config)
                raise ARIUnreachable(ari_config)
            except requests.HTTPError as e:
                if asterisk_is_loading(e):
                    logger.info('ARI is not ready yet, retrying in %s seconds...', connection_delay)
                    time.sleep(connection_delay)
                    continue
                else:
                    raise
        raise ARIUnreachable(ari_config)

    def run(self):
        logger.debug('ARI client listening...')
        self._connect()
        while self._should_reconnect:
            self._reconnect()

    def _connect(self):
        try:
            with self._running():
                self.client.run(apps=[APPLICATION_NAME])
        except socket.error as e:
            if e.errno == errno.EPIPE:
                # bug in ari-py when calling client.close(): ignore it and stop
                logger.error('Error while listening for ARI events: %s', e)
                return
            else:
                self._connection_error(e)
        except (WebSocketException, HTTPError) as e:
            self._connection_error(e)

    @contextmanager
    def _running(self):
        self._is_running = True
        yield
        self._is_running = False

    def _connection_error(self, error):
        logger.warning('ARI connection error: %s...', error)

    def _reconnect(self):
        delay = self.config['reconnection_delay']
        logger.warning('Reconnecting to ARI in %s seconds', delay)
        time.sleep(delay)

        self._connect()

    def _sync(self):
        '''self.sync() should be called before calling self.stop(), in case the
        ari client does not have the websocket yet'''

        while self._is_running and not self.client.websockets:
            time.sleep(0.1)

    def stop(self):
        try:
            self._should_reconnect = False
            self._sync()
            self.client.close()
        except RuntimeError:
            pass  # bug in ari-py when calling client.close()
