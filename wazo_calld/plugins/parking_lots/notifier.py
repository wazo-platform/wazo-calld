# Copyright 2024 The Wazo Authors (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from wazo_bus.resources.calls.parking import (
    CallParkedEvent,
    CallUnparkedEvent,
    ParkedCallHungupEvent,
    ParkedCallTimedOutEvent,
)


if TYPE_CHECKING:
    from wazo_calld.bus import CoreBusPublisher
    from .dataclasses_ import AsteriskParkedCall


class ParkingNotifier:
    def __init__(self, bus_publisher: CoreBusPublisher):
        self._publisher = bus_publisher

    def _get_parking_id(self, parkinglot_name: str) -> str | None:
        _, *id_ = parkinglot_name.split('-', 1)
        if not id_:
            return None
        return str(*id_)

    def _to_timestamp(self, value: str) -> str:
        now = datetime.now(timezone.utc)
        timestamp = now + timedelta(seconds=int(value))
        return timestamp.isoformat()

    def _since_timestamp(self, value: str) -> str:
        now = datetime.now(timezone.utc)
        timestamp = now - timedelta(seconds=int(value))
        return timestamp.isoformat()

    def call_parked(self, parked_call: AsteriskParkedCall, tenant_uuid: str) -> None:
        event = CallParkedEvent(
            parked_call.parkee_uniqueid,
            self._get_parking_id(parked_call.parkinglot),
            parked_call.parking_space,
            self._to_timestamp(parked_call.parking_timeout),
            tenant_uuid,
        )
        self._publisher.publish(event)

    def call_unparked(
        self, parked_call: AsteriskParkedCall, retriever_call: str, tenant_uuid: str
    ) -> None:
        event = CallUnparkedEvent(
            parked_call.parkee_uniqueid,
            self._get_parking_id(parked_call.parkinglot),
            parked_call.parking_space,
            retriever_call,
            tenant_uuid,
        )
        self._publisher.publish(event)

    def parked_call_timed_out(
        self, parked_call: AsteriskParkedCall, tenant_uuid: str
    ) -> None:
        event = ParkedCallTimedOutEvent(
            parked_call.parkee_uniqueid,
            self._get_parking_id(parked_call.parkinglot),
            parked_call.parker_dial_string,
            self._since_timestamp(parked_call.parking_duration),
            tenant_uuid,
        )
        self._publisher.publish(event)

    def parked_call_hangup(
        self, parked_call: AsteriskParkedCall, tenant_uuid: str
    ) -> None:
        event = ParkedCallHungupEvent(
            parked_call.parkee_uniqueid,
            self._get_parking_id(parked_call.parkinglot),
            parked_call.parking_space,
            self._since_timestamp(parked_call.parking_duration),
            tenant_uuid,
        )
        self._publisher.publish(event)
