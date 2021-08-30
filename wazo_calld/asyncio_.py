# Copyright 2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import asyncio
import logging

logger = logging.getLogger(__name__)


class CoreAsyncio:

    def __init__(self):
        self._loop = asyncio.new_event_loop()

    def run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def call_later(self, delay, callback, *args):

        # This function will run within the asyncio thread
        def delay_wrapper():
            self._loop.call_later(delay, callback, *args)

        self._loop.call_soon_threadsafe(delay_wrapper)

    def stop(self):
        if not self._loop:
            return

        self._loop.stop()
        self._loop.close()
        self._loop = asyncio.new_event_loop()
