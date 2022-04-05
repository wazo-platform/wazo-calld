# Copyright 2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from threading import Lock as _Lock, Event, Thread, RLock

logger = logging.getLogger(__name__)


class Lock:

    def __init__(self, name):
        self._name = name
        self._lock = _Lock()

    def acquire(self):
        logger.debug('acquiring lock "%s"', self._name)
        self._lock.acquire()

    def release(self):
        logger.debug('releasing lock "%s"', self._name)
        self._lock.release()

    def __enter__(self):
        self.acquire()

    def __exit__(self, *arg, **kwargs):
        self.release()


__all__ = [
    'Event',
    'Thread',
    'RLock',
]
