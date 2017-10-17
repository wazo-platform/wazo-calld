# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import threading
import uuid

from contextlib import contextmanager
from xivo.pubsub import Pubsub

logger = logging.getLogger(__name__)


class RelocateRole(object):
    relocated = 'relocated'
    initiator = 'initiator'
    recipient = 'recipient'


class Relocate(object):

    def __init__(self, state_factory):
        self.uuid = str(uuid.uuid4())
        self._state_factory = state_factory
        self.relocated_channel = None
        self.initiator_channel = None
        self.recipient_channel = None
        self.initiator = None
        self.set_state('ready')
        self._lock = threading.Lock()
        self.events = Pubsub()

    def set_state(self, state_name):
        logger.debug('Relocate %s: setting state to "%s"', self.uuid, state_name)
        self._state = self._state_factory.make(state_name)

        if state_name == 'ended':
            self.end()

    def initiate(self, destination):
        self._state.initiate(self, destination)

    def recipient_answered(self):
        self._state.recipient_answered(self)

    def relocated_answered(self):
        self._state.relocated_answered(self)

    def initiator_hangup(self):
        self._state.initiator_hangup(self)

    def recipient_hangup(self):
        self._state.recipient_hangup(self)

    def relocated_hangup(self):
        self._state.relocated_hangup(self)

    def end(self):
        self.events.publish('ended', self)

    def role(self, channel_id):
        if channel_id == self.relocated_channel:
            return RelocateRole.relocated
        elif channel_id == self.initiator_channel:
            return RelocateRole.initiator
        elif channel_id == self.recipient_channel:
            return RelocateRole.recipient
        else:
            raise KeyError(channel_id)

    def acquire(self):
        self._lock.acquire()
        logger.debug('Relocate %s: acquired lock', self.uuid)

    def release(self):
        self._lock.release()
        logger.debug('Relocate %s: released lock', self.uuid)

    @contextmanager
    def locked(self):
        self.acquire()
        try:
            yield
        finally:
            self.release()


class RelocateCollection(object):

    def __init__(self):
        self._relocates = {}

    def add(self, relocate):
        self._relocates[relocate.uuid] = relocate
        relocate.events.subscribe('ended', self.remove)

    def remove(self, relocate):
        self._relocates.pop(relocate.uuid, None)

    def get(self, relocate_uuid, user_uuid=None):
        result = self._relocates[relocate_uuid]

        if user_uuid and result.initiator != user_uuid:
            raise KeyError(relocate_uuid)

        return result

    def get_by_channel(self, channel_id):
        result = self.find_by_channel(channel_id)

        if not result:
            raise KeyError(channel_id)

        return result

    def find_by_channel(self, channel_id):
        for relocate in self._relocates.itervalues():
            if channel_id in (relocate.relocated_channel,
                              relocate.initiator_channel,
                              relocate.recipient_channel):
                return relocate

        return None

    def list(self, user_uuid):
        return [relocate
                for relocate in self._relocates.values()
                if relocate.initiator == user_uuid]
