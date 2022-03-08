# Copyright 2020-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from xivo_bus.resources.calls.hold import CallOnHoldEvent, CallResumeEvent
from xivo_bus.resources.calls.dtmf import CallDTMFEvent
from xivo_bus.resources.calls.missed import UserMissedCall
from .schemas import call_schema
from .event import (
    CallAnswered,
    CallCreated,
    CallEnded,
    CallUpdated,
)

logger = logging.getLogger(__name__)


class CallNotifier:
    def __init__(self, bus):
        self._bus = bus

    def _build_headers(self, call):
        return {
            'tenant_uuid': call.tenant_uuid,
            'user_uuid:{uuid}'.format(uuid=call.user_uuid): True,
        }

    def call_created(self, call):
        event = CallCreated(call_schema.dump(call))
        headers = self._build_headers(call)
        self._bus.publish(event, headers=headers)

    def call_ended(self, call, reason_code):
        call_serialized = call_schema.dump(call)
        call_serialized.update(reason_code=reason_code)
        event = CallEnded(call_serialized)
        headers = self._build_headers(call)
        self._bus.publish(event, headers=headers)

    def call_updated(self, call):
        event = CallUpdated(call_schema.dump(call))
        headers = self._build_headers(call)
        self._bus.publish(event, headers=headers)

    def call_answered(self, call):
        event = CallAnswered(call_schema.dump(call))
        headers = self._build_headers(call)
        self._bus.publish(event, headers=headers)

    def call_hold(self, call):
        event = CallOnHoldEvent(call.id_, call.user_uuid)
        headers = self._build_headers(call)
        self._bus.publish(event, headers=headers)

    def call_resume(self, call):
        event = CallResumeEvent(call.id_, call.user_uuid)
        headers = self._build_headers(call)
        self._bus.publish(event, headers=headers)

    def call_dtmf(self, call, digit):
        event = CallDTMFEvent(call.id_, digit, call.user_uuid)
        headers = self._build_headers(call)
        self._bus.publish(event, headers=headers)

    def user_missed_call(self, payload):
        tenant_uuid = payload.pop('tenant_uuid')
        event = UserMissedCall(payload)
        headers = {
            'tenant_uuid': tenant_uuid,
            'user_uuid:{uuid}'.format(uuid=payload['user_uuid']): True
        }
        self._bus.publish(event, headers=headers)
