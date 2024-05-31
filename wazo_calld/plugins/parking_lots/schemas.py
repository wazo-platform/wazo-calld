# Copyright 2024 The Wazo Authors (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from marshmallow import EXCLUDE, Schema, post_dump, pre_dump
from marshmallow.fields import Method
from marshmallow.validate import Predicate, Range
from xivo.mallow.fields import Integer, List, Nested, String

from .helpers import timestamp, timestamp_since

if TYPE_CHECKING:
    from .dataclasses_ import AsteriskParkedCall


class _Base(Schema):
    class Meta:
        ordered = True
        unknown = EXCLUDE


class ParkingLotSchema(_Base):
    id = Integer(dump_only=True)
    name = String(dump_only=True)
    slots_start = Integer(dump_only=True)
    slots_end = Integer(dump_only=True)
    slots_total = Integer(dump_only=True, default=0)
    slots_remaining = Integer(dump_only=True, default=0)
    default_timeout = Integer(attribute='timeout', dump_only=True)
    calls = List(Nested("ParkedCallGetResponseSchema"), default=list)

    @pre_dump
    def calls_from_context(self, obj, **kwargs):
        if 'calls' in self.context:
            obj.calls = self.context['calls']
        return obj

    @post_dump
    def compute_slots(self, obj, **kwargs):
        total = 1 + (obj['slots_end'] - obj['slots_start'])
        obj['slots_total'] = total
        obj['slots_remaining'] = total - len(obj['calls'])
        return obj


class ParkingLotListSchema(ParkingLotSchema):
    @pre_dump
    def unwrap_calls(self, obj, **kwargs):
        parkinglot, calls = obj
        parkinglot.calls = calls
        return parkinglot


class ParkedCallGetResponseSchema(_Base):
    call_id = String(attribute='parkee_uniqueid', dump_only=True)
    caller_id_name = String(attribute='parkee_caller_id_name', dump_only=True)
    caller_id_num = String(attribute='parkee_caller_id_num', dump_only=True)
    connected_line_name = String(attribute='parkee_connected_line_name', dump_only=True)
    connected_line_num = String(attribute='parkee_connected_line_num', dump_only=True)
    slot = String(attribute='parking_space', dump_only=True)
    parked_at = Method('compute_park_time', dump_only=True)
    timeout_at = Method('compute_timeout', allow_none=True, dump_only=True)
    timeout = Integer(attribute='parking_timeout', dump_only=True)

    def compute_park_time(self, parked_call: AsteriskParkedCall) -> str:
        return timestamp_since(parked_call.parking_duration)

    def compute_timeout(self, parked_call: AsteriskParkedCall) -> str | None:
        return timestamp(parked_call.parking_timeout)


class ParkCallRequestSchema(_Base):
    parking_id = Integer(allow_none=False, required=True, load_only=True)
    preferred_slot = String(
        validate=Predicate('isdigit'), allow_none=True, missing=None, load_only=True
    )
    timeout = Integer(
        validate=Range(min=0, error='Must be a positive integer or 0'),
        allow_none=True,
        missing=None,
        load_only=True,
    )


class ParkedCallPutResponseSchema(_Base):
    slot = String(attribute='parking_space', dump_only=True)
    timeout_at = Method('compute_timeout', allow_none=True, dump_only=True)

    def compute_timeout(self, parked_call: AsteriskParkedCall) -> str | None:
        return timestamp(parked_call.parking_timeout)


park_call_request_schema = ParkCallRequestSchema()
parked_call_get_response_schema = ParkedCallGetResponseSchema()
parked_call_put_response_schema = ParkedCallPutResponseSchema()
