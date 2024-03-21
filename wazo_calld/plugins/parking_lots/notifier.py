# Copyright 2024 The Wazo Authors (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from wazo_bus.resources.calls.parking import (
    CallParkedEvent,
    CallUnparkedEvent,
    ParkedCallHungupEvent,
    ParkedCallTimedOutEvent,
)

from .helpers import split_parking_id_from_name, timestamp, timestamp_since

if TYPE_CHECKING:
    from wazo_calld.bus import CoreBusPublisher

    from .dataclasses_ import AsteriskParkedCall


class ParkingNotifier:
    def __init__(self, bus_publisher: CoreBusPublisher):
        self._publisher = bus_publisher

    def call_parked(self, parked_call: AsteriskParkedCall, tenant_uuid: str) -> None:
        event = CallParkedEvent(
            parked_call.parkee_uniqueid,
            split_parking_id_from_name(parked_call.parkinglot),
            parked_call.parking_space,
            timestamp(parked_call.parking_timeout),
            tenant_uuid,
        )
        self._publisher.publish(event)

    def call_unparked(
        self, parked_call: AsteriskParkedCall, retriever_call: str, tenant_uuid: str
    ) -> None:
        event = CallUnparkedEvent(
            parked_call.parkee_uniqueid,
            split_parking_id_from_name(parked_call.parkinglot),
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
            split_parking_id_from_name(parked_call.parkinglot),
            parked_call.parker_dial_string,
            timestamp_since(parked_call.parking_duration),
            tenant_uuid,
        )
        self._publisher.publish(event)

    def parked_call_hangup(
        self, parked_call: AsteriskParkedCall, tenant_uuid: str
    ) -> None:
        event = ParkedCallHungupEvent(
            parked_call.parkee_uniqueid,
            split_parking_id_from_name(parked_call.parkinglot),
            parked_call.parking_space,
            timestamp_since(parked_call.parking_duration),
            tenant_uuid,
        )
        self._publisher.publish(event)
