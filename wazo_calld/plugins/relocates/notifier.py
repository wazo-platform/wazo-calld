# Copyright 2017-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from xivo_bus.resources.calls.event import (
    CallRelocateAnsweredEvent,
    CallRelocateCompletedEvent,
    CallRelocateEndedEvent,
    CallRelocateInitiatedEvent,
)

from .schemas import relocate_schema

logger = logging.getLogger(__name__)


class RelocatesNotifier:
    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    def observe(self, relocate):
        relocate.events.subscribe('initiated', self.initiated)
        relocate.events.subscribe('answered', self.answered)
        relocate.events.subscribe('completed', self.completed)
        relocate.events.subscribe('ended', self.ended)

    def initiated(self, relocate):
        payload = relocate_schema.dump(relocate)
        tenant_uuid = relocate.recipient_variables['WAZO_TENANT_UUID']
        event = CallRelocateInitiatedEvent(payload, tenant_uuid, relocate.initiator)
        self._bus_producer.publish(event)

    def answered(self, relocate):
        payload = relocate_schema.dump(relocate)
        tenant_uuid = relocate.recipient_variables['WAZO_TENANT_UUID']
        event = CallRelocateAnsweredEvent(payload, tenant_uuid, relocate.initiator)
        self._bus_producer.publish(event)

    def completed(self, relocate):
        payload = relocate_schema.dump(relocate)
        tenant_uuid = relocate.recipient_variables['WAZO_TENANT_UUID']
        event = CallRelocateCompletedEvent(payload, tenant_uuid, relocate.initiator)
        self._bus_producer.publish(event)

    def ended(self, relocate):
        payload = relocate_schema.dump(relocate)
        tenant_uuid = relocate.recipient_variables['WAZO_TENANT_UUID']
        event = CallRelocateEndedEvent(payload, tenant_uuid, relocate.initiator)
        self._bus_producer.publish(event)
