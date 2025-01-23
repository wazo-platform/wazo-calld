# Copyright 2020-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from wazo_bus.resources.calls.event import (
    CallAnsweredEvent,
    CallCreatedEvent,
    CallDTMFEvent,
    CallEndedEvent,
    CallHeldEvent,
    CallResumedEvent,
    CallRecordPausedEvent,
    CallRecordResumedEvent,
    CallRecordStartedEvent,
    CallRecordStoppedEvent,
    CallUpdatedEvent,
    MissedCallEvent,
)

from .schemas import call_schema

logger = logging.getLogger(__name__)


class CallNotifier:
    def __init__(self, bus):
        self._bus = bus

    def call_created(self, call):
        payload = call_schema.dump(call)
        event = CallCreatedEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_ended(self, call, reason_code):
        payload = call_schema.dump(call)
        payload.update(reason_code=reason_code)
        event = CallEndedEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_updated(self, call):
        payload = call_schema.dump(call)
        event = CallUpdatedEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_answered(self, call):
        payload = call_schema.dump(call)
        event = CallAnsweredEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_hold(self, call):
        event = CallHeldEvent(call.id_, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_resume(self, call):
        event = CallResumedEvent(call.id_, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_dtmf(self, call, digit):
        event = CallDTMFEvent(call.id_, digit, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def user_missed_call(self, payload):
        tenant_uuid = payload.pop('tenant_uuid')
        event = MissedCallEvent(payload, tenant_uuid, payload['user_uuid'])
        self._bus.publish(event)

    def call_record_paused(self, call):
        event = CallRecordPausedEvent(call.id_, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_record_resumed(self, call):
        event = CallRecordResumedEvent(call.id_, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_record_started(self, call):
        event = CallRecordStartedEvent(call.id_, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_record_stopped(self, call):
        event = CallRecordStoppedEvent(call.id_, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)
