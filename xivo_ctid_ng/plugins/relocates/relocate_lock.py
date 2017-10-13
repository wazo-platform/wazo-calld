# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import threading

logger = logging.getLogger(__name__)


class RelocateLock(object):
    def __init__(self):
        self._locked_calls = set()
        self._lock = threading.Lock()

    def acquire(self, call):
        logger.debug('acquiring relocate lock on %s...', call)
        with self._lock:
            if call in self._locked_calls:
                logger.debug('failed to acquire relocate lock on %s', call)
                return False
            self._locked_calls.add(call)
            logger.debug('acquired relocate lock on %s', call)
            return True

    def release(self, call):
        logger.debug('releasing relocate lock on %s...', call)
        with self._lock:
            self._locked_calls.discard(call)
            logger.debug('released relocate lock on %s', call)
