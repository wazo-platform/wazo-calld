# Copyright 2020-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from xivo_bus.resources.calls.event import (
    CallHeldEvent,
    CallResumedEvent,
    CallDTMFEvent,
    MissedCallEvent,
    CallAnsweredEvent,
    CallCreatedEvent,
    CallEndedEvent,
    CallUpdatedEvent,
)
from xivo_bus.resources.common.event import UserEvent

from .schemas import call_schema


logger = logging.getLogger(__name__)


class CallConnectedEvent(UserEvent):
    service = 'calld'
    name = 'call_connected'
    routing_key_fmt = 'calls.connected'
    required_acl_fmt = 'events.calls.{user_uuid}'

    def __init__(self, geolocation, tenant_uuid, user_uuid):
        content = {'geolocation': geolocation}
        super().__init__(content, tenant_uuid, user_uuid)


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

        if call.is_caller:
            for target_uuid in call.talking_to.values():
                self._bus.publish(
                    CallConnectedEvent(call.geolocation, call.tenant_uuid, target_uuid)
                )

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
