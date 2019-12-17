# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import threading

logger = logging.getLogger(__name__)


hashed_args_kwargs_mark = object()  # sentinel for separating args from kwargs


class ConfdClientGetUUIDCacheDecorator:

    def __init__(self, decorated_get, resource_name):
        self._decorated_get = decorated_get
        self._resource_name = resource_name
        self._cache = {}
        self._lock = threading.Lock()

    def subscribe(self, bus_consumer, events):
        for event in events:
            bus_consumer.on_event(event, self._on_entry_changed)

    def _on_entry_changed(self, event_body):
        uuid = event_body['uuid']
        self.invalidate_cache_entry(uuid)

    def invalidate_cache_entry(self, uuid):
        with self._lock:
            logger.debug('Removing %s %s from cache', self._resource_name, uuid)
            del self._cache[uuid]

    def __call__(self, uuid, *args, **kwargs):
        hashed_args = args + (hashed_args_kwargs_mark,) + tuple(sorted(kwargs.items()))

        try:
            response = self._cache[uuid][hashed_args]
        except KeyError:
            pass
        else:
            logger.debug('Found %s %s in cache', self._resource_name, uuid)
            return response

        response = self._decorated_get(uuid, *args, **kwargs)

        with self._lock:
            logger.debug('Adding %s %s to cache', self._resource_name, uuid)
            self._cache.setdefault(uuid, {})
            self._cache[uuid][hashed_args] = response

        return response


class ConfdClientGetIDCacheDecorator(ConfdClientGetUUIDCacheDecorator):

    def _on_entry_changed(self, event_body):
        id = event_body['id']
        self.invalidate_cache_entry(id)


class ConfdClientUserLineGetCacheDecorator(ConfdClientGetUUIDCacheDecorator):

    def subscribe(self, bus_consumer):
        for event in ('user_edited', 'user_deleted'):
            bus_consumer.on_event(event, self._on_user_changed)
        for event in ('user_line_associated', 'user_line_dissociated'):
            bus_consumer.on_event(event, self._on_user_line_changed)

    def _on_user_changed(self, event_body):
        uuid = event_body['uuid']
        self.invalidate_cache_entry(uuid)

    def _on_user_line_changed(self, event_body):
        uuid = event_body['user']['uuid']
        self.invalidate_cache_entry(uuid)
