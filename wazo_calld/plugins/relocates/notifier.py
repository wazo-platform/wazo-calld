# Copyright 2017-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from xivo_bus.resources.calls.relocate import (
    RelocateAnsweredEvent,
    RelocateCompletedEvent,
    RelocateInitiatedEvent,
    RelocateEndedEvent
)
from .schemas import relocate_schema

logger = logging.getLogger(__name__)


class RelocatesNotifier:

    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    @staticmethod
    def _build_headers(user_uuids=None, **kwargs):
        headers = {}
        for uuid in user_uuids or []:
            headers[f'user_uuid:{uuid}'] = True

        for key, value in kwargs.items():
            if value:
                headers[key] = value
        return headers if headers else None

    def observe(self, relocate):
        relocate.events.subscribe('initiated', self.initiated)
        relocate.events.subscribe('answered', self.answered)
        relocate.events.subscribe('completed', self.completed)
        relocate.events.subscribe('ended', self.ended)

    def initiated(self, relocate):
        relocate_dict = relocate_schema.dump(relocate)
        event = RelocateInitiatedEvent(relocate.initiator, relocate_dict)
        headers = self._build_headers(
            user_uuids=[relocate.initiator],
            tenant_uuid=relocate.recipient_variables.get('WAZO_TENANT_UUID'),
        )
        self._bus_producer.publish(event, headers=headers)

    def answered(self, relocate):
        relocate_dict = relocate_schema.dump(relocate)
        event = RelocateAnsweredEvent(relocate.initiator, relocate_dict)
        headers = self._build_headers(
            user_uuids=[relocate.initiator],
            tenant_uuid=relocate.recipient_variables.get('WAZO_TENANT_UUID'),
        )
        self._bus_producer.publish(event, headers=headers)

    def completed(self, relocate):
        relocate_dict = relocate_schema.dump(relocate)
        event = RelocateCompletedEvent(relocate.initiator, relocate_dict)
        headers = self._build_headers(
            user_uuids=[relocate.initiator],
            tenant_uuid=relocate.recipient_variables.get('WAZO_TENANT_UUID'),
        )
        self._bus_producer.publish(event, headers=headers)

    def ended(self, relocate):
        relocate_dict = relocate_schema.dump(relocate)
        event = RelocateEndedEvent(relocate.initiator, relocate_dict)
        headers = self._build_headers(
            user_uuids=[relocate.initiator],
            tenant_uuid=relocate.recipient_variables.get('WAZO_TENANT_UUID'),
        )
        self._bus_producer.publish(event, headers=headers)
