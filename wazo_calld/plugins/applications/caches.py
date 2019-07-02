# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from .exceptions import NoSuchApplication, NoSuchMoh

UNINITIALIZED_FMT = 'Received an event when {} cache is not initialized'
UNINITIALIZED_APP = UNINITIALIZED_FMT.format('application')
UNINITIALIZED_MOH = UNINITIALIZED_FMT.format('moh')

logger = logging.getLogger(__name__)


class ConfdApplicationsCache:

    def __init__(self, confd):
        self._confd = confd
        self._cache = None
        self._triggers = {'created': [], 'updated': [], 'deleted': []}

    @property
    def _applications(self):
        if self._cache is None:
            result = self._confd.applications.list(recurse=True)['items']
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
        bus_consumer.on_event('application_created', self._application_created)
        bus_consumer.on_event('application_deleted', self._application_deleted)
        bus_consumer.on_event('application_edited', self._application_updated)

    def created_subscribe(self, callback):
        self._triggers['created'].append(callback)

    def updated_subscribe(self, callback):
        self._triggers['updated'].append(callback)

    def deleted_subscribe(self, callback):
        self._triggers['deleted'].append(callback)

    def _application_created(self, event):
        if self._cache is None:
            logger.debug(UNINITIALIZED_APP)
            return

        self._applications[event['uuid']] = event
        for trigger in self._triggers['created']:
            trigger(event)

    def _application_updated(self, event):
        if self._cache is None:
            logger.debug(UNINITIALIZED_APP)
            return

        old = self._applications.get(event['uuid'])
        self._applications[event['uuid']] = event
        for trigger in self._triggers['updated']:
            trigger(old, event)

    def _application_deleted(self, event):
        if self._cache is None:
            logger.debug(UNINITIALIZED_APP)
            return

        self._applications.pop(event['uuid'], None)
        for trigger in self._triggers['deleted']:
            trigger(event)


class MohCache:

    def __init__(self, confd):
        self._confd = confd
        self._cache = None

    @property
    def _moh(self):
        if self._cache is None:
            result = self._confd.moh.list(recurse=True)['items']
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
        bus_consumer.on_event('moh_created', self._moh_created)
        bus_consumer.on_event('moh_deleted', self._moh_deleted)

    def _moh_created(self, event):
        if self._cache is None:
            logger.debug(UNINITIALIZED_MOH)
            return

        self._moh[event['uuid']] = event

    def _moh_deleted(self, event):
        if self._cache is None:
            logger.debug(UNINITIALIZED_MOH)
            return

        self._moh.pop(event['uuid'], None)
