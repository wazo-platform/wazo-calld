# Copyright 2024 The Wazo Authors (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from wazo_bus.resources.calls.parking import (
    CallParkedEvent,
    CallUnparkedEvent,
    ParkedCallHungupEvent,
    ParkedCallTimedOutEvent,
)
from wazo_bus.resources.calls.types import ParkedCallDict, UnparkedCallDict

from wazo_calld.bus import CoreBusPublisher

from .dataclasses_ import AsteriskParkedCall, AsteriskUnparkedCall
from .helpers import split_parking_id_from_name, timestamp, timestamp_since


class ParkingNotifier:
    def __init__(self, bus_publisher: CoreBusPublisher):
        self._publisher = bus_publisher

    def _convert_to_dict(
        self, parked_call: AsteriskParkedCall, **extra_kwargs
    ) -> ParkedCallDict:
        return {
            'parking_id': split_parking_id_from_name(parked_call.parkinglot),
            'call_id': parked_call.parkee_uniqueid,
            'conversation_id': parked_call.parkee_linkedid,
            'caller_id_name': parked_call.parkee_caller_id_name,
            'caller_id_num': parked_call.parkee_caller_id_num,
            'parker_caller_id_name': parked_call.parkee_connected_line_name,
            'parker_caller_id_num': parked_call.parkee_connected_line_num,
            'slot': parked_call.parking_space,
            'parked_at': timestamp_since(parked_call.parking_duration),
            'timeout_at': timestamp(parked_call.parking_timeout),
            **extra_kwargs,
        }

    def call_parked(self, parked_call: AsteriskParkedCall, tenant_uuid: str) -> None:
        payload = self._convert_to_dict(parked_call)
        event = CallParkedEvent(payload, tenant_uuid=tenant_uuid)
        self._publisher.publish(event)

    def call_unparked(
        self,
        unparked_call: AsteriskUnparkedCall,
        tenant_uuid: str,
    ) -> None:
        payload: UnparkedCallDict = self._convert_to_dict(
            unparked_call,
            retriever_call_id=unparked_call.retriever_uniqueid,
            retriever_caller_id_name=unparked_call.retriever_caller_id_name,
            retriever_caller_id_num=unparked_call.retriever_caller_id_num,
        )
        event = CallUnparkedEvent(payload, tenant_uuid)
        self._publisher.publish(event)

    def parked_call_timed_out(
        self, parked_call: AsteriskParkedCall, tenant_uuid: str
    ) -> None:
        payload = self._convert_to_dict(
            parked_call, dialed_extension=parked_call.parker_dial_string
        )
        event = ParkedCallTimedOutEvent(payload, tenant_uuid)
        self._publisher.publish(event)

    def parked_call_hangup(
        self, parked_call: AsteriskParkedCall, tenant_uuid: str
    ) -> None:
        payload = self._convert_to_dict(parked_call)
        event = ParkedCallHungupEvent(payload, tenant_uuid)
        self._publisher.publish(event)
