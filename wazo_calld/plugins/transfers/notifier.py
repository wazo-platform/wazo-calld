# Copyright 2016-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from wazo_bus import BusPublisher
from wazo_bus.resources.calls.event import (
    CallTransferAbandonedEvent,
    CallTransferAnsweredEvent,
    CallTransferCancelledEvent,
    CallTransferCompletedEvent,
    CallTransferCreatedEvent,
    CallTransferEndedEvent,
    CallTransferUpdatedEvent,
)

logger = logging.getLogger(__name__)


class TransferNotifier:
    def __init__(self, bus_producer):
        self._bus_producer: BusPublisher = bus_producer

    def created(self, transfer):
        event = CallTransferCreatedEvent(
            transfer.to_public_dict(),
            transfer.initiator_tenant_uuid,
            transfer.initiator_uuid,
        )
        self._bus_producer.publish(event)

    def updated(self, transfer):
        event = CallTransferUpdatedEvent(
            transfer.to_public_dict(),
            transfer.initiator_tenant_uuid,
            transfer.initiator_uuid,
        )
        self._bus_producer.publish(event)

    def answered(self, transfer):
        event = CallTransferAnsweredEvent(
            transfer.to_public_dict(),
            transfer.initiator_tenant_uuid,
            transfer.initiator_uuid,
        )
        self._bus_producer.publish(event)

    def cancelled(self, transfer):
        event = CallTransferCancelledEvent(
            transfer.to_public_dict(),
            transfer.initiator_tenant_uuid,
            transfer.initiator_uuid,
        )
        self._bus_producer.publish(event)

    def completed(self, transfer):
        event = CallTransferCompletedEvent(
            transfer.to_public_dict(),
            transfer.initiator_tenant_uuid,
            transfer.initiator_uuid,
        )
        self._bus_producer.publish(event)

    def abandoned(self, transfer):
        event = CallTransferAbandonedEvent(
            transfer.to_public_dict(),
            transfer.initiator_tenant_uuid,
            transfer.initiator_uuid,
        )
        self._bus_producer.publish(event)

    def ended(self, transfer):
        event = CallTransferEndedEvent(
            transfer.to_public_dict(),
            transfer.initiator_tenant_uuid,
            transfer.initiator_uuid,
        )
        self._bus_producer.publish(event)
