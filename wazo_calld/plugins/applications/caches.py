# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from .exceptions import NoSuchApplication

NOT_INITIALIZED_MSG = 'Received an event when application cache is not initialized'

logger = logging.getLogger(__name__)


class ConfdApplicationsCache:

    def __init__(self, confd):
        self._confd = confd
        self._cache = None

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
        bus_consumer.on_event('application_created', self._application_updated)
        bus_consumer.on_event('application_deleted', self._application_deleted)
        bus_consumer.on_event('application_edited', self._application_updated)

    def _application_updated(self, event):
        if self._cache is None:
            logger.debug(NOT_INITIALIZED_MSG)
            return

        self._applications[event['uuid']] = event

    def _application_deleted(self, event):
        if self._cache is None:
            logger.debug(NOT_INITIALIZED_MSG)
            return

        self._applications.pop(event['uuid'], None)
