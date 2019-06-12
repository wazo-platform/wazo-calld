# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from xivo.permission import escape as escape_permission
from xivo_bus.resources.common.routing_key import escape as escape_routing_key
from xivo_bus.resources.common.event import ArbitraryEvent
from .resources import (
    held_call_schema,
    queued_call_schema,
)

logger = logging.getLogger(__name__)


class SwitchboardsNotifier:

    def __init__(self, bus):
        self._bus = bus

    def queued_calls(self, tenant_uuid, switchboard_uuid, calls):
        body = {
            'switchboard_uuid': switchboard_uuid,
            'items': queued_call_schema.dump(calls, many=True).data
        }
        logger.debug(
            'Notifying updated queued calls for switchboard %s: %s calls',
            switchboard_uuid,
            len(calls),
        )
        event = ArbitraryEvent(
            name='switchboard_queued_calls_updated',
            body=body,
            required_acl='events.switchboards.{uuid}.calls.queued.updated'.format(
                uuid=switchboard_uuid,
            ),
        )
        event.routing_key = 'switchboards.{uuid}.calls.queued.updated'.format(uuid=switchboard_uuid)
        self._bus.publish(event)

    def queued_call_answered(self, switchboard_uuid, operator_call_id, queued_call_id):
        logger.debug(
            'Queued call %s in switchboard %s answered by %s',
            queued_call_id,
            switchboard_uuid,
            operator_call_id,
        )
        body = {
            'switchboard_uuid': switchboard_uuid,
            'operator_call_id': operator_call_id,
            'queued_call_id': queued_call_id
        }
        required_acl = 'events.switchboards.{uuid}.calls.queued.{call_id}.answer.updated'.format(
            uuid=switchboard_uuid,
            call_id=escape_permission(queued_call_id),
        )
        routing_key = 'switchboards.{uuid}.calls.queued.{call_id}.answer.updated'.format(
            uuid=switchboard_uuid,
            call_id=escape_routing_key(queued_call_id),
        )
        event = ArbitraryEvent(
            name='switchboard_queued_call_answered',
            body=body,
            required_acl=required_acl,
        )
        event.routing_key = routing_key
        self._bus.publish(event)

    def held_calls(self, tenant_uuid, switchboard_uuid, calls):
        body = {
            'switchboard_uuid': switchboard_uuid,
            'items': held_call_schema.dump(calls, many=True).data
        }
        logger.debug(
            'Notifying updated held calls for switchboard %s: %s calls',
            switchboard_uuid,
            len(calls),
        )
        event = ArbitraryEvent(
            name='switchboard_held_calls_updated',
            body=body,
            required_acl='events.switchboards.{uuid}.calls.held.updated'.format(
                uuid=switchboard_uuid,
            ),
        )
        event.routing_key = 'switchboards.{uuid}.calls.held.updated'.format(uuid=switchboard_uuid)
        self._bus.publish(event)

    def held_call_answered(self, switchboard_uuid, operator_call_id, held_call_id):
        logger.debug(
            'Held call %s in switchboard %s answered by %s',
            held_call_id,
            switchboard_uuid,
            operator_call_id,
        )
        body = {
            'switchboard_uuid': switchboard_uuid,
            'operator_call_id': operator_call_id,
            'held_call_id': held_call_id
        }
        required_acl = 'events.switchboards.{uuid}.calls.held.{call_id}.answer.updated'.format(
            uuid=switchboard_uuid,
            call_id=escape_permission(held_call_id),
        )
        routing_key = 'switchboards.{uuid}.calls.held.{call_id}.answer.updated'.format(
            uuid=switchboard_uuid,
            call_id=escape_routing_key(held_call_id),
        )
        event = ArbitraryEvent(
            name='switchboard_held_call_answered',
            body=body,
            required_acl=required_acl,
        )
        event.routing_key = routing_key
        self._bus.publish(event)
