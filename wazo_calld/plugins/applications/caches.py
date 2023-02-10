# Copyright 2019-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import requests
import threading

from .exceptions import NoSuchApplication, NoSuchMoh, WazoConfdUnreachable

UNINITIALIZED_FMT = 'Received an event when {} cache is not initialized'
UNINITIALIZED_APP = UNINITIALIZED_FMT.format('application')
UNINITIALIZED_MOH = UNINITIALIZED_FMT.format('moh')

logger = logging.getLogger(__name__)


# If this helper is used more than once, then it should go to the wazo-confd-client
class ConfdIsReadyThread:
    def __init__(self, confd_client):
        self._confd_client = confd_client
        self._started = False
        self._should_stop = threading.Event()
        self._retry_time = 1
        self.callback = None

    def start(self):
        if self._started:
            raise Exception('Check when wazo-confd is ready already started')

        self._started = True
        thread_name = 'check_when_confd_is_ready'
        self._thread = threading.Thread(target=self._run, name=thread_name)
        self._thread.start()

    def stop(self):
        self._should_stop.set()
        logger.debug('joining check_when_confd_is_ready thread...')
        self._thread.join()

    def subscribe(self, callback):
        self.callback = callback

    def _run(self):
        while not self._should_stop.is_set():
            if self._is_ready():
                self.callback()
                return
            logger.info(
                'wazo-confd is not ready yet, retrying in %s seconds...',
                self._retry_time,
            )
            self._should_stop.wait(timeout=self._retry_time)

    def _is_ready(self):
        try:
            self._confd_client.infos.get()
        except requests.ConnectionError:
            return False
        except requests.HTTPError:
            pass
        return True


class ConfdApplicationsCache:
    def __init__(self, confd):
        self._confd = confd
        self._cache = None
        self._cache_lock = threading.Lock()
        self._triggers = {'created': [], 'updated': [], 'deleted': []}

    @property
    def _applications(self):
        with self._cache_lock:
            if self._cache is None:
                try:
                    result = self._confd.applications.list(recurse=True)['items']
                except requests.ConnectionError:
                    raise WazoConfdUnreachable()
                self._cache = {app['uuid']: app for app in result}
        return self._cache

    def list(self):
        return list(self._applications.values())

    def get(self, application_uuid):
        application = self._applications.get(str(application_uuid))
        if not application:
            raise NoSuchApplication(application_uuid)
        return application

    def subscribe(self, bus_consumer):
        bus_consumer.subscribe('application_created', self._application_created)
        bus_consumer.subscribe('application_deleted', self._application_deleted)
        bus_consumer.subscribe('application_edited', self._application_updated)

    def created_subscribe(self, callback):
        self._triggers['created'].append(callback)

    def updated_subscribe(self, callback):
        self._triggers['updated'].append(callback)

    def deleted_subscribe(self, callback):
        self._triggers['deleted'].append(callback)

    def _application_created(self, event):
        if not self._is_initialized():
            return

        self._applications[event['uuid']] = event
        for trigger in self._triggers['created']:
            trigger(event)

    def _application_updated(self, event):
        if not self._is_initialized():
            return

        old = self._applications.get(event['uuid'])
        self._applications[event['uuid']] = event
        for trigger in self._triggers['updated']:
            trigger(old, event)

    def _application_deleted(self, event):
        if not self._is_initialized():
            return

        self._applications.pop(event['uuid'], None)
        for trigger in self._triggers['deleted']:
            trigger(event)

    def _is_initialized(self):
        with self._cache_lock:
            if self._cache is None:
                logger.debug(UNINITIALIZED_APP)
                return False
            return True


class MohCache:
    def __init__(self, confd):
        self._confd = confd
        self._cache = None
        self._cache_lock = threading.Lock()

    @property
    def _moh(self):
        with self._cache_lock:
            if self._cache is None:
                try:
                    result = self._confd.moh.list(recurse=True)['items']
                except requests.ConnectionError:
                    raise WazoConfdUnreachable()
                self._cache = {moh['uuid']: moh for moh in result}
                logger.info('MOH cache initialized: %s', self._cache)
        return self._cache

    def list(self):
        return list(self._moh.values())

    def get(self, moh_uuid):
        moh = self._moh.get(str(moh_uuid))
        if not moh:
            raise NoSuchMoh(moh_uuid)
        return moh

    def find_by_name(self, moh_name):
        for moh in self._moh.values():
            if moh['name'] == moh_name:
                return moh

    def subscribe(self, bus_consumer):
        bus_consumer.subscribe('moh_created', self._moh_created)
        bus_consumer.subscribe('moh_deleted', self._moh_deleted)

    def _moh_created(self, event):
        if not self._is_initialized():
            return

        self._moh[event['uuid']] = event

    def _moh_deleted(self, event):
        if not self._is_initialized():
            return

        self._moh.pop(event['uuid'], None)

    def _is_initialized(self):
        with self._cache_lock:
            if self._cache is None:
                logger.debug(UNINITIALIZED_MOH)
                return False
            return True
