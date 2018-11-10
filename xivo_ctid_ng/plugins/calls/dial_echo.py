# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import uuid

from queue import Queue, Empty as EmptyQueue

logger = logging.getLogger(__name__)


class DialEchoTimeout(Exception):
    pass


class DialEchoFailure(Exception):
    pass


class DialEchoManager(object):
    '''This feature has some problems:

    - If the echo is not set, the channel is still up. Should we hang it up?
    - In case of closed schedules, denied call permissions, etc. the echo will
      never be set

    A cleaner way to solve the original problem (knowing the non-Local channel
    id of a Local originate), would be to be able to set it. A simple way to do
    that would be to patch the Dial application and add an option to set the
    Uniqueid of the new Dial'ed channel. '''

    def __init__(self):
        self._queues = {}

    def new_dial_echo_request(self):
        dial_echo_request_id = str(uuid.uuid4())
        self._queues[dial_echo_request_id] = Queue()
        logger.debug('Created dial echo request %s', dial_echo_request_id)
        return dial_echo_request_id

    def wait(self, dial_echo_request_id, timeout):
        queue = self._queues.get(dial_echo_request_id)
        if not queue:
            logger.debug('Dial echo: ignoring dial echo wait from unknown request %s', dial_echo_request_id)
            return

        logger.debug('Waiting for dial echo request %s', dial_echo_request_id)
        try:
            result = queue.get(block=True, timeout=timeout)
        except EmptyQueue:
            self._queues.pop(dial_echo_request_id, None)
            raise DialEchoTimeout()
        logger.debug('Got result from dial echo request %s: %s', dial_echo_request_id, result)

        try:
            channel_id = result['channel_id']
        except KeyError:
            self._queues.pop(dial_echo_request_id, None)
            raise DialEchoFailure(result)
        logger.debug('Got channel ID from dial echo request %s: %s', dial_echo_request_id, channel_id)

        self._queues.pop(dial_echo_request_id, None)

        return channel_id

    def set_dial_echo_result(self, dial_echo_request_id, result):
        queue = self._queues.get(dial_echo_request_id)
        if not queue:
            logger.debug('Dial echo: ignoring dial_echo result from unknown request %s', dial_echo_request_id)
            return
        queue.put(result)
