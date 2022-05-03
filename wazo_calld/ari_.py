# Copyright 2015-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import errno
import logging
import socket
import time
import urllib
import threading

from contextlib import contextmanager

import ari
import requests
import swaggerpy.http_client

from requests.exceptions import HTTPError
from websocket import WebSocketException
from xivo.pubsub import Pubsub
from xivo.status import Status

from .exceptions import AsteriskARINotInitialized

logger = logging.getLogger(__name__)

DEFAULT_APPLICATION_NAME = 'callcontrol'
ALL_STASIS_EVENTS = [
    "ApplicationReplaced",
    "BridgeAttendedTransfer",
    "BridgeBlindTransfer",
    "BridgeCreated",
    "BridgeDestroyed",
    "BridgeMerged",
    "ChannelCallerId",
    "ChannelConnectedLine",
    "ChannelCreated",
    "ChannelDestroyed",
    "ChannelDialplan",
    "ChannelDtmfReceived",
    "ChannelEnteredBridge",
    "ChannelHangupRequest",
    "ChannelHold",
    "ChannelLeftBridge",
    "ChannelMohStart",
    "ChannelMohStop",
    "ChannelStateChange",
    "ChannelTalkingFinished",
    "ChannelTalkingStarted",
    "ChannelUnhold",
    "ChannelUserevent",
    "ChannelVarset",
    "ContactStatusChange",
    "DeviceStateChanged",
    "Dial",
    "EndpointStateChange",
    "PeerStatusChange",
    "PlaybackFinished",
    "PlaybackStarted",
    "RecordingFailed",
    "RecordingFinished",
    "RecordingStarted",
    "StasisEnd",
    "StasisStart",
    "TextMessageReceived",
]


def not_found(error):
    return error.response is not None and error.response.status_code == 404


def service_unavailable(error):
    return error.response is not None and error.response.status_code == 503


def asterisk_is_loading(error):
    return not_found(error) or service_unavailable(error)


class ARIClientProxy(ari.client.Client):

    def __init__(self, base_url, username, password):
        self._base_url = base_url
        self._username = username
        self._password = password
        self._initialized = False
        self._registered_app = set()

    def init(self):
        if not self._initialized:
            split = urllib.parse.urlsplit(self._base_url)
            http_client = swaggerpy.http_client.SynchronousHttpClient()
            http_client.set_basic_auth(split.hostname, self._username, self._password)
            super().__init__(self._base_url, http_client)
            self._initialized = True
        return self._initialized

    def close(self):
        if not self._initialized:
            return

        return super().close()

    def __getattr__(self, *args, **kwargs):
        if not self._initialized:
            raise AsteriskARINotInitialized()

        return super().__getattr__(*args, **kwargs)

    def on_application_registered(self, application_name, fn, *args, **kwargs):
        super().on_application_registered(application_name, fn, *args, **kwargs)
        if application_name in self._registered_app:
            # The app is already registered, execute the callback now
            try:
                fn(*args, **kwargs)
            except Exception as e:
                self.exception_handler(e)

    def execute_app_registered_callbacks(self, apps):
        for app in apps:
            self._registered_app.add(app)
        return self._execute_app_registered_callbacks(','.join(apps))

    def execute_app_deregistered_callbacks(self, apps):
        for app in apps:
            self._registered_app.discard(app)
        return self._execute_app_deregistered_callbacks(','.join(apps))


class CoreARI:

    def __init__(self, config, bus_consumer):
        self._apps = []
        self.config = config
        self._is_running = False
        self._should_delay_reconnect = True
        self._should_stop = False
        self._pubsub = Pubsub()
        self._bus_consumer = bus_consumer
        self.client = ARIClientProxy(**config['connection'])
        self._initialization_thread = threading.Thread(target=self.run)

    def init_client(self):
        self._subscribe_to_bus_events()
        self._initialization_thread.start()
        return True

    def _subscribe_to_bus_events(self):
        for event_name in ALL_STASIS_EVENTS:
            self._bus_consumer.subscribe(
                event_name,
                self.client.on_stasis_event,
                headers={'category': 'stasis'},
            )
        self._bus_consumer.subscribe('FullyBooted', self.reregister_applications)

    def client_initialized_subscribe(self, callback):
        self._pubsub.subscribe('client_initialized', callback)

    def run(self):
        while not self._should_stop:
            try:
                initialized = self.client.init()
            except Exception:
                initialized = False

            if initialized:
                self._pubsub.publish('client_initialized', message=None)
                break

            connection_delay = self.config['startup_connection_delay']
            logger.warning('ARI not initialized, retrying in %s seconds...', connection_delay)
            time.sleep(connection_delay)
        self._should_delay_reconnect = False

    def _connect(self):
        logger.debug('ARI client listening...')
        try:
            with self._running():
                self.client.run(apps=self._apps)
        except socket.error as e:
            if e.errno == errno.EPIPE:
                # bug in ari-py when calling client.close(): ignore it and stop
                logger.error('Error while listening for ARI events: %s', e)
                return
            else:
                self._connection_error(e)
        except (WebSocketException, HTTPError) as e:
            self._connection_error(e)
        except ValueError:
            logger.warning('Received non-JSON message from ARI... disconnecting')
            self.client.close()

    @contextmanager
    def _running(self):
        self._is_running = True
        try:
            yield
        finally:
            self._is_running = False

    def reregister_applications(self, _event):
        logger.info('Asterisk started, registering all stasis applications')
        self.client.execute_app_deregistered_callbacks(self._apps)
        for app in self._apps:
            self.client.amqp.stasisSubscribe(applicationName=app)
        self.client.execute_app_registered_callbacks(self._apps)

    def register_application(self, app):
        if app in self._apps:
            return

        self._apps.append(app)
        self.client.amqp.stasisSubscribe(applicationName=app)
        self.client.execute_app_registered_callbacks([app])

    def deregister_application(self, app):
        if app in self._apps:
            self._apps.remove(app)
            self.client.execute_app_deregistered_callbacks([app])
            self.client.amqp.stasisUnsubscribe(applicationName=app)

    def is_running(self):
        return self._is_running

    def provide_status(self, status):
        expected_apps = [
            'adhoc_conference',
            'callcontrol',
            'dial_mobile'
        ]
        ok = self.client._initialized and set(expected_apps).issubset(set(self._apps))
        status['ari']['status'] = Status.ok if ok else Status.fail

    def _connection_error(self, error):
        logger.warning('ARI connection error: %s...', error)

    def _sync(self):
        '''self.sync() should be called before calling self.stop(), in case the
        ari client does not have the websocket yet'''

        while self._is_running:
            try:
                ari_websockets = self.client.websockets
            except AsteriskARINotInitialized:
                ari_websockets = None
            if ari_websockets:
                return
            time.sleep(0.1)

    def stop(self):
        self._should_stop = True
        self._initialization_thread.join()

    def _trigger_disconnect(self):
        self._sync()
        try:
            self.client.close()
        except RuntimeError:
            pass  # bug in ari-py when calling client.close()
