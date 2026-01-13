# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
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
            bus_consumer.subscribe(event, self._on_entry_changed)

    def _on_entry_changed(self, event_body):
        uuid = event_body['uuid']
        self.invalidate_cache_entry(uuid)

    def invalidate_cache_entry(self, uuid):
        with self._lock:
            logger.debug('Removing %s %s from cache', self._resource_name, uuid)
            self._cache.pop(uuid, None)

    def _make_key(self, args, kwargs):
        # See lru_cache code for more details:
        # https://github.com/python/cpython/blob/051ff526b5dc2c40c4a53d87089740358822edfa/Lib/functools.py#L438

        return args + (hashed_args_kwargs_mark,) + tuple(sorted(kwargs.items()))

    def __call__(self, uuid, *args, **kwargs):
        args_key = self._make_key(args, kwargs)

        try:
            response = self._cache[uuid][args_key]
        except KeyError:
            pass
        else:
            logger.debug('Found %s %s in cache', self._resource_name, uuid)
            return response

        response = self._decorated_get(uuid, *args, **kwargs)

        with self._lock:
            logger.debug('Adding %s %s to cache', self._resource_name, uuid)
            self._cache.setdefault(uuid, {})
            self._cache[uuid][args_key] = response

        return response


class ConfdClientGetIDCacheDecorator(ConfdClientGetUUIDCacheDecorator):
    def _on_entry_changed(self, event_body):
        id = event_body['id']
        self.invalidate_cache_entry(id)


class ConfdClientUserLineGetCacheDecorator(ConfdClientGetUUIDCacheDecorator):
    def subscribe(self, bus_consumer, events=None):
        for event in ('user_edited', 'user_deleted'):
            bus_consumer.subscribe(event, self._on_user_changed)
        for event in ('user_line_associated', 'user_line_dissociated'):
            bus_consumer.subscribe(event, self._on_user_line_changed)

    def _on_user_changed(self, event_body):
        uuid = event_body['uuid']
        self.invalidate_cache_entry(uuid)

    def _on_user_line_changed(self, event_body):
        uuid = event_body['user']['uuid']
        self.invalidate_cache_entry(uuid)
