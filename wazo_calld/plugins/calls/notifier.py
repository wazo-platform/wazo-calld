# Copyright 2020-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

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

from .schemas import call_schema

logger = logging.getLogger(__name__)


class CallNotifier:
    def __init__(self, bus):
        self._bus = bus

    @staticmethod
    def _check_tenant_uuid(tenant_uuid, call_id):
        # tenant-scoped bus events refuse to build without a tenant_uuid
        if not tenant_uuid:
            logger.warning(
                'Not publishing call event for channel %s: no tenant_uuid', call_id
            )
            return False
        return True

    def call_created(self, call):
        if not self._check_tenant_uuid(call.tenant_uuid, call.id_):
            return
        payload = call_schema.dump(call)
        event = CallCreatedEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_ended(self, call, reason_code):
        if not self._check_tenant_uuid(call.tenant_uuid, call.id_):
            return
        payload = call_schema.dump(call)
        payload.update(reason_code=reason_code)
        event = CallEndedEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_updated(self, call):
        if not self._check_tenant_uuid(call.tenant_uuid, call.id_):
            return
        payload = call_schema.dump(call)
        event = CallUpdatedEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_answered(self, call):
        if not self._check_tenant_uuid(call.tenant_uuid, call.id_):
            return
        payload = call_schema.dump(call)
        event = CallAnsweredEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_hold(self, call):
        if not self._check_tenant_uuid(call.tenant_uuid, call.id_):
            return
        event = CallHeldEvent(call.id_, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_resume(self, call):
        if not self._check_tenant_uuid(call.tenant_uuid, call.id_):
            return
        event = CallResumedEvent(call.id_, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_dtmf(self, call, digit):
        if not self._check_tenant_uuid(call.tenant_uuid, call.id_):
            return
        event = CallDTMFEvent(call.id_, digit, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def user_missed_call(self, payload):
        tenant_uuid = payload.pop('tenant_uuid')
        if not self._check_tenant_uuid(tenant_uuid, payload['conversation_id']):
            return
        event = MissedCallEvent(payload, tenant_uuid, payload['user_uuid'])
        self._bus.publish(event)

    def call_record_paused(self, call):
        if not self._check_tenant_uuid(call.tenant_uuid, call.id_):
            return
        payload = {"call_id": call.id_}
        event = CallRecordPausedEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_record_resumed(self, call):
        if not self._check_tenant_uuid(call.tenant_uuid, call.id_):
            return
        payload = {"call_id": call.id_}
        event = CallRecordResumedEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_record_started(self, call):
        if not self._check_tenant_uuid(call.tenant_uuid, call.id_):
            return
        payload = {"call_id": call.id_}
        event = CallRecordStartedEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)

    def call_record_stopped(self, call):
        if not self._check_tenant_uuid(call.tenant_uuid, call.id_):
            return
        payload = {"call_id": call.id_}
        event = CallRecordStoppedEvent(payload, call.tenant_uuid, call.user_uuid)
        self._bus.publish(event)
