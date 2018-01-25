# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import Queue
import uuid

logger = logging.getLogger(__name__)


class DialEchoTimeout(Exception):
    pass


class DialEchoFailure(Exception):
    pass


class DialEchoManager(object):

    def __init__(self):
        self._queues = {}

    def new_dial_echo_request(self):
        dial_echo_request_id = str(uuid.uuid4())
        self._queues[dial_echo_request_id] = Queue.Queue()
        logger.debug('Created dial echo request %s', dial_echo_request_id)
        return dial_echo_request_id

    def wait(self, dial_echo_request_id, timeout):
        queue = self._queues[dial_echo_request_id]
        logger.debug('Waiting for dial echo request %s', dial_echo_request_id)
        try:
            result = queue.get(block=True, timeout=timeout)
        except Queue.Empty:
            raise DialEchoTimeout()
        logger.debug('Got result from dial echo request %s: %s', dial_echo_request_id, result)

        try:
            channel_id = result['channel_id']
        except KeyError:
            raise DialEchoFailure(result)
        logger.debug('Got channel ID from dial echo request %s: %s', dial_echo_request_id, channel_id)

        self._queues.pop(dial_echo_request_id, None)

        return channel_id

    def set_dial_echo_result(self, dial_echo_request_id, result):
        self._queues[dial_echo_request_id].put(result)
