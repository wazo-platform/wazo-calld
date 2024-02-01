# Copyright 2020-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from wazo_bus.resources.calls.event import (
    CallAnsweredEvent,
    CallCreatedEvent,
    CallDTMFEvent,
    CallEndedEvent,
    CallHeldEvent,
    CallResumedEvent,
    CallUpdatedEvent,
    MissedCallEvent,
)

from .call import Call
from .schemas import call_schema

logger = logging.getLogger(__name__)


class CallNotifier:
    def __init__(self, bus):
        self._bus = bus

    def call_created(self, channel_name: str, call: Call) -> None:
        if not call.tenant_uuid:
            logger.debug(
                'call_created event has no tenant_uuid: %s (%s)', call.id_, channel_name
            )
            return
        payload = call_schema.dump(call)
        event = CallCreatedEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_ended(self, channel_name: str, call: Call, reason_code: str) -> None:
        if not call.tenant_uuid:
            logger.debug(
                'call_ended event has no tenant_uuid: %s (%s)', call.id_, channel_name
            )
            return
        payload = call_schema.dump(call)
        payload.update(reason_code=reason_code)
        event = CallEndedEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_updated(self, channel_name: str, call: Call) -> None:
        if not call.tenant_uuid:
            logger.debug(
                'call_updated event has no tenant_uuid: %s (%s)', call.id_, channel_name
            )
            return
        payload = call_schema.dump(call)
        event = CallUpdatedEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_answered(self, channel_name: str, call: Call) -> None:
        if not call.tenant_uuid:
            logger.debug(
                'call_answered event has no tenant_uuid: %s (%s)',
                call.id_,
                channel_name,
            )
            return
        payload = call_schema.dump(call)
        event = CallAnsweredEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_hold(self, channel_name: str, call: Call) -> None:
        if not call.tenant_uuid:
            logger.debug(
                'call_hold event has no tenant_uuid: %s (%s)', call.id_, channel_name
            )
            return
        event = CallHeldEvent(call.id_, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_resume(self, channel_name: str, call: Call) -> None:
        if not call.tenant_uuid:
            logger.debug(
                'call_resume event has no tenant_uuid: %s (%s)', call.id_, channel_name
            )
            return
        event = CallResumedEvent(call.id_, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_dtmf(self, channel_name: str, call: Call, digit: str):
        if not call.tenant_uuid:
            logger.debug(
                'call_dtmf event has no tenant_uuid: %s (%s)', call.id_, channel_name
            )
            return
        event = CallDTMFEvent(call.id_, digit, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def user_missed_call(self, payload: dict, tenant_uuid: str, user_uuid: str):
        if not tenant_uuid:
            logger.debug(
                'user_missed_call event has no tenant_uuid: user `%s`', user_uuid
            )
            return
        event = MissedCallEvent(payload, tenant_uuid, user_uuid)
        self._bus.publish(event)
