# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo_bus.resources.calls.relocate import (
    RelocateAnsweredEvent,
    RelocateCompletedEvent,
    RelocateInitiatedEvent,
    RelocateEndedEvent
)
from .schema import relocate_schema

logger = logging.getLogger(__name__)


class RelocatesNotifier(object):

    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    def observe(self, relocate):
        relocate.events.subscribe('initiated', self.initiated)
        relocate.events.subscribe('answered', self.answered)
        relocate.events.subscribe('completed', self.completed)
        relocate.events.subscribe('ended', self.ended)

    def initiated(self, relocate):
        relocate_dict = relocate_schema.dump(relocate).data
        event = RelocateInitiatedEvent(relocate.initiator, relocate_dict)
        headers = {'user_uuid:{}'.format(relocate.initiator): True}
        self._bus_producer.publish(event, headers=headers)

    def answered(self, relocate):
        relocate_dict = relocate_schema.dump(relocate).data
        event = RelocateAnsweredEvent(relocate.initiator, relocate_dict)
        headers = {'user_uuid:{}'.format(relocate.initiator): True}
        self._bus_producer.publish(event, headers=headers)

    def completed(self, relocate):
        relocate_dict = relocate_schema.dump(relocate).data
        event = RelocateCompletedEvent(relocate.initiator, relocate_dict)
        headers = {'user_uuid:{}'.format(relocate.initiator): True}
        self._bus_producer.publish(event, headers=headers)

    def ended(self, relocate):
        relocate_dict = relocate_schema.dump(relocate).data
        event = RelocateEndedEvent(relocate.initiator, relocate_dict)
        headers = {'user_uuid:{}'.format(relocate.initiator): True}
        self._bus_producer.publish(event, headers=headers)
