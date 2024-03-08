# Copyright 2024 The Wazo Authors (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging

from requests import RequestException
from typing import cast, TypedDict, TYPE_CHECKING
from typing_extensions import NotRequired

from wazo_calld.plugin_helpers.ari_ import Channel
from wazo_calld.plugin_helpers.exceptions import (
    WazoAmidError,
    NotEnoughChannels,
    TooManyChannels,
    UserPermissionDenied,
)

from .cache import ParkingLotCache
from .dataclasses_ import AsteriskParkedCall
from .exceptions import (
    InvalidCall,
    NoSuchCall,
    NoSuchParkedCall,
    NoSuchParkingException,
    ParkingFull,
)
from .notifier import ParkingNotifier

if TYPE_CHECKING:
    from wazo_amid_client import Client as AmidClient
    from wazo_calld.ari_ import CoreARI as AriClient
    from wazo_calld.bus import CoreBusConsumer as BusConsumer
    from wazo_confd_client import Client as ConfdClient
    from .dataclasses_ import ConfdParkingLot


PARKED_CHANNEL_VAR = 'WAZO_CALL_PARKED'
logger = logging.getLogger(__name__)


class ParkActionDict(TypedDict):
    Channel: str
    Parkinglot: str
    Timeout: NotRequired[int]
    ParkingSpace: NotRequired[str]
    TimeoutChannel: NotRequired[str]
    AnnounceChannel: NotRequired[str]


class ParkingService:
    def __init__(
        self,
        ami: AmidClient,
        ari: AriClient,
        bus: BusConsumer,
        confd: ConfdClient,
        notifier: ParkingNotifier,
    ):
        self._amid = ami
        self._ari = ari
        self._confd = confd
        self._notifier = notifier
        self._parkings = ParkingLotCache(bus, confd)

    def _get_peer_channel(self, channel: Channel) -> Channel:
        try:
            return channel.only_connected_channel()
        except NotEnoughChannels:
            raise InvalidCall(channel.id, 'no parkable peer call found')
        except TooManyChannels:
            raise InvalidCall(channel.id, 'cannot park a conference call')

    def find_parked_call(
        self, tenant_uuid: str, parking_id: int, call_id: str
    ) -> AsteriskParkedCall | None:
        for call in self.list_parked_calls(tenant_uuid, parking_id):
            if call.parkee_uniqueid == call_id:
                return call
        return None

    def get_parked_call(
        self, tenant_uuid: str, parking_id: int, call_id: str
    ) -> AsteriskParkedCall:
        parked_call = self.find_parked_call(tenant_uuid, parking_id, call_id)
        if not parked_call:
            raise NoSuchParkedCall(tenant_uuid, parking_id, call_id)
        return parked_call

    def get_parking(self, tenant_uuid: str, parking_id: int) -> ConfdParkingLot:
        parking = self._parkings[parking_id]
        if parking.tenant_uuid != tenant_uuid:
            raise NoSuchParkingException(parking_id)
        return parking

    def list_parked_calls(
        self, tenant_uuid: str, parking_id: int
    ) -> list[AsteriskParkedCall]:
        parking = self.get_parking(tenant_uuid, parking_id)

        try:
            results: list[dict] = self._amid.action(
                'parkedcalls', {'ParkingLot': f'parkinglot-{parking.id}'}
            )
        except RequestException as e:
            raise WazoAmidError(self._amid, e)

        parked_calls = [
            AsteriskParkedCall.from_dict(result)
            for result in results
            if result.get('Event') == 'ParkedCall'
        ]
        return parked_calls

    def count_parked_calls(self, tenant_uuid: str, parking_id: int) -> int:
        parking = self.get_parking(tenant_uuid, parking_id)

        try:
            results: list[dict] = self._amid.action(
                'parkedcalls', {'ParkingLot': f'parkinglot-{parking.id}'}
            )
        except RequestException as e:
            raise WazoAmidError(self._amid, e)

        complete = results.pop()
        if complete.get('Event') != 'ParkedCallsComplete':
            raise WazoAmidError(self._amid, 'missing ParkedCallsComplete message')
        return int(complete['Total'])

    def is_parking_full(self, tenant_uuid: str, parking_id: int) -> bool:
        parking = self.get_parking(tenant_uuid, parking_id)
        total_slots = int(parking.slots_end) - int(parking.slots_start)
        count = self.count_parked_calls(tenant_uuid, parking_id)
        return count >= total_slots

    def park_call(
        self,
        parking_id: int,
        call_id: str,
        *,
        tenant_uuid: str | None = None,
        preferred_slot: str | None = None,
        timeout: int | None = None,
    ) -> AsteriskParkedCall:
        channel = Channel(call_id, self._ari.client)
        if not channel.exists():
            raise NoSuchCall(call_id)

        if not tenant_uuid:
            tenant_uuid = cast(str, channel.tenant_uuid())
            if not tenant_uuid:
                raise InvalidCall(call_id, 'call has no tenant_uuid')

        parking = self.get_parking(tenant_uuid, parking_id)

        park_payload: ParkActionDict = {
            'Channel': channel.asterisk_name(),
            'Parkinglot': f'parkinglot-{parking.id}',
        }

        if timeout:
            # convert to milliseconds for AMI action
            park_payload['Timeout'] = timeout * 1000

        if preferred_slot:
            # Attempt to use slot if it can, else it wil be auto-attributed
            park_payload['ParkingSpace'] = preferred_slot

        parked_call = self.find_parked_call(tenant_uuid, parking.id, call_id)
        if not parked_call:
            callback_channel = self._get_peer_channel(channel)
            park_payload['TimeoutChannel'] = callback_channel.asterisk_name()
        else:
            # If call is already parked, preserve callback
            park_payload['TimeoutChannel'] = parked_call.parker_dial_string

        try:
            self._amid.action('park', park_payload)
        except RequestException as e:
            raise WazoAmidError(self._amid, e)

        # NOTE: Should probably wait for ParkedCall event to happen instead of polling
        try:
            return self.get_parked_call(tenant_uuid, parking.id, call_id)
        except NoSuchParkedCall:
            if self.is_parking_full(tenant_uuid, parking_id):
                raise ParkingFull(tenant_uuid, parking_id, call_id)
            raise

    def park_peer_call(
        self,
        user_uuid: str,
        parking_id: int,
        call_id: str,
        *,
        preferred_slot: str | None = None,
        timeout: int | None = None,
    ) -> AsteriskParkedCall:
        user_channel = Channel(call_id, self._ari.client)

        if not user_channel.exists():
            raise NoSuchCall(call_id)

        if user_uuid != user_channel.user():
            raise UserPermissionDenied(user_uuid, {'call': call_id})

        tenant_uuid = user_channel.tenant_uuid()
        if not tenant_uuid:
            raise InvalidCall(call_id, 'call has no tenant_uuid')

        peer_channel = self._get_peer_channel(user_channel)
        return self.park_call(
            parking_id, peer_channel.id, preferred_slot=preferred_slot, timeout=timeout
        )
