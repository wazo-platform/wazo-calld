# Copyright 2020-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from typing import Any

from wazo_bus.resources.calls.event import (
    CallAnsweredEvent,
    CallCreatedEvent,
    CallDTMFEvent,
    CallEndedEvent,
    CallHeldEvent,
    CallRecordPausedEvent,
    CallRecordResumedEvent,
    CallRecordStartedEvent,
    CallRecordStoppedEvent,
    CallResumedEvent,
    CallUpdatedEvent,
    MissedCallEvent,
)
from wazo_bus.resources.common.event import UserEvent

from .call import Call
from .schemas import call_schema

logger = logging.getLogger(__name__)


class CallNotifier:
    def __init__(self, bus):
        self._bus = bus

    def _publish(self, event_class: type[UserEvent], call: Call, *content: Any) -> None:
        if not call.tenant_uuid:
            logger.debug(
                '%s event has no tenant_uuid: %s (%s)',
                event_class.name,
                call.id_,
                call.channel_name,
            )
            return
        self._bus.publish(event_class(*content, call.tenant_uuid, call.user_uuid))

    def call_created(self, call: Call) -> None:
        self._publish(CallCreatedEvent, call, call_schema.dump(call))

    def call_ended(self, call: Call, reason_code: int) -> None:
        payload = call_schema.dump(call)
        payload.update(reason_code=reason_code)
        self._publish(CallEndedEvent, call, payload)

    def call_updated(self, call: Call) -> None:
        self._publish(CallUpdatedEvent, call, call_schema.dump(call))

    def call_answered(self, call: Call) -> None:
        self._publish(CallAnsweredEvent, call, call_schema.dump(call))

    def call_hold(self, call: Call) -> None:
        self._publish(CallHeldEvent, call, call.id_)

    def call_resume(self, call: Call) -> None:
        self._publish(CallResumedEvent, call, call.id_)

    def call_dtmf(self, call: Call, digit: str) -> None:
        self._publish(CallDTMFEvent, call, call.id_, digit)

    def user_missed_call(self, payload: dict) -> None:
        tenant_uuid = payload.pop('tenant_uuid')
        if not tenant_uuid:
            logger.debug(
                'user_missed_call event has no tenant_uuid: user `%s`',
                payload['user_uuid'],
            )
            return
        event = MissedCallEvent(payload, tenant_uuid, payload['user_uuid'])
        self._bus.publish(event)

    def call_record_paused(self, call: Call) -> None:
        self._publish(CallRecordPausedEvent, call, {'call_id': call.id_})

    def call_record_resumed(self, call: Call) -> None:
        self._publish(CallRecordResumedEvent, call, {'call_id': call.id_})

    def call_record_started(self, call: Call) -> None:
        self._publish(CallRecordStartedEvent, call, {'call_id': call.id_})

    def call_record_stopped(self, call: Call) -> None:
        self._publish(CallRecordStoppedEvent, call, {'call_id': call.id_})
