# Copyright 2017-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from xivo_bus.resources.switchboard.event import (
    SwitchboardQueuedCallsUpdatedEvent,
    SwitchboardQueuedCallAnsweredEvent,
    SwitchboardHeldCallsUpdatedEvent,
    SwitchboardHeldCallAnsweredEvent
)
from .http import (
    held_call_schema,
    queued_call_schema,
)

logger = logging.getLogger(__name__)


class SwitchboardsNotifier:
    def __init__(self, bus):
        self._bus = bus

    @staticmethod
    def _build_headers(tenant_uuid):
        return {'tenant_uuid': tenant_uuid}

    def queued_calls(self, tenant_uuid, switchboard_uuid, calls):
        body = {
            'switchboard_uuid': switchboard_uuid,
            'items': queued_call_schema.dump(calls, many=True),
        }
        logger.debug(
            'Notifying updated queued calls for switchboard %s: %s calls',
            switchboard_uuid,
            len(calls),
        )

        event = SwitchboardQueuedCallsUpdatedEvent(body)
        headers = self._build_headers(tenant_uuid)
        self._bus.publish(event, headers=headers)

    def queued_call_answered(
        self, tenant_uuid, switchboard_uuid, operator_call_id, queued_call_id
    ):
        logger.debug(
            'Queued call %s in switchboard %s answered by %s',
            queued_call_id,
            switchboard_uuid,
            operator_call_id,
        )
        body = {
            'switchboard_uuid': switchboard_uuid,
            'operator_call_id': operator_call_id,
            'queued_call_id': queued_call_id,
        }

        event = SwitchboardQueuedCallAnsweredEvent(body)
        headers = self._build_headers(tenant_uuid)
        self._bus.publish(event, headers=headers)

    def held_calls(self, tenant_uuid, switchboard_uuid, calls):
        logger.debug(
            'Notifying updated held calls for switchboard %s: %s calls',
            switchboard_uuid,
            len(calls),
        )

        body = {
            'switchboard_uuid': switchboard_uuid,
            'items': held_call_schema.dump(calls, many=True),
        }
        event = SwitchboardHeldCallsUpdatedEvent(body)
        headers = self._build_headers(tenant_uuid)
        self._bus.publish(event, headers=headers)

    def held_call_answered(
        self, tenant_uuid, switchboard_uuid, operator_call_id, held_call_id
    ):
        logger.debug(
            'Held call %s in switchboard %s answered by %s',
            held_call_id,
            switchboard_uuid,
            operator_call_id,
        )

        body = {
            'switchboard_uuid': switchboard_uuid,
            'operator_call_id': operator_call_id,
            'held_call_id': held_call_id,
        }
        event = SwitchboardHeldCallAnsweredEvent(body)
        headers = self._build_headers(tenant_uuid)
        self._bus.publish(event, headers=headers)
