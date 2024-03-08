# Copyright 2024 The Wazo Authors (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from marshmallow import EXCLUDE, pre_dump, post_dump, Schema
from marshmallow.fields import Method
from marshmallow.validate import Predicate
from xivo.mallow.fields import Integer, List, Nested, String

if TYPE_CHECKING:
    from .dataclasses_ import AsteriskParkedCall, ConfdParkingLot


class _Base(Schema):
    class Meta:
        ordered = True
        unknown = EXCLUDE


class ParkingLotSchema(_Base):
    name = String(dump_only=True)
    exten = String(dump_only=True, default='')
    slots_start = Integer(dump_only=True)
    slots_end = Integer(dump_only=True)
    slots_total = Integer(dump_only=True, default=0)
    slots_remaining = Integer(dump_only=True, default=0)
    default_timeout = Integer(attribute='timeout', dump_only=True)
    calls = List(Nested("ParkedCallGetResponseSchema"))

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

    @post_dump(pass_original=True)
    def extract_exten(self, data: dict, original_obj: ConfdParkingLot, **kwargs):
        if original_obj.extensions:
            data['exten'] = original_obj.extensions[0].exten

        return data


class ParkedCallGetResponseSchema(_Base):
    call_id = String(attribute='parkee_uniqueid', dump_only=True)
    slot = String(attribute='parking_space', dump_only=True)
    parked_at = Method('compute_park_time', dump_only=True)
    timeout_at = Method('compute_timeout', dump_only=True)

    def compute_park_time(self, parked_call: AsteriskParkedCall) -> str:
        now = datetime.now(timezone.utc)
        parked_at = now - timedelta(seconds=int(parked_call.parking_duration))
        return parked_at.isoformat()

    def compute_timeout(self, parked_call: AsteriskParkedCall) -> str:
        now = datetime.now(timezone.utc)
        timeout_at = now + timedelta(seconds=int(parked_call.parking_timeout))
        return timeout_at.isoformat()


class ParkCallRequestSchema(_Base):
    parking_id = Integer(allow_none=False, required=True, load_only=True)
    preferred_slot = String(
        validate=Predicate('isdigit'), allow_none=True, missing=None, load_only=True
    )
    timeout = Integer(allow_none=True, missing=None, load_only=True)


class ParkedCallPutResponseSchema(_Base):
    slot = String(attribute='parking_space', dump_only=True)
    timeout_at = Method('compute_timeout', dump_only=True)

    def compute_timeout(self, parked_call: AsteriskParkedCall) -> str:
        now = datetime.now(timezone.utc)
        timeout_at = now + timedelta(seconds=int(parked_call.parking_timeout))
        return timeout_at.isoformat()


park_call_request_schema = ParkCallRequestSchema()
parked_call_get_response_schema = ParkedCallGetResponseSchema()
parked_call_put_response_schema = ParkedCallPutResponseSchema()
