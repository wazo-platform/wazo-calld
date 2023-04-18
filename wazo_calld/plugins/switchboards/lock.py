# Copyright 2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from contextlib import contextmanager
import logging
import threading
import random
import time

logger = logging.getLogger(__name__)


def generate_transaction_id():
    rand_num = random.randint(0, 2**24 - 1)
    rand_hex = format(rand_num, '06x')
    return rand_hex


class SwitchboardsLock:
    def __init__(self):
        self._lock = threading.Lock()

    @contextmanager
    def acquired(self, switchboard_uuid, call_id):
        transaction_id = generate_transaction_id()
        logger.debug(
            'Trying to acquire action lock '
            '(transaction id=%s, switchboard_uuid=%s, call_id=%s)',
            transaction_id,
            switchboard_uuid,
            call_id,
        )
        acquire_start_time = time.time()
        result = self._lock.acquire()
        acquire_end_time = time.time()
        logger.debug(
            'Action lock acquired after %.3f '
            '(transaction id=%s, switchboard_uuid=%s, call_id=%s)',
            acquire_end_time - acquire_start_time,
            transaction_id,
            switchboard_uuid,
            call_id,
        )
        try:
            yield result
        finally:
            self._lock.release()
            release_end_time = time.time()
            logger.debug(
                'Action lock released after %.3f '
                '(transaction id=%s, switchboard_uuid=%s, call_id=%s)',
                release_end_time - acquire_end_time,
                transaction_id,
                switchboard_uuid,
                call_id,
            )
