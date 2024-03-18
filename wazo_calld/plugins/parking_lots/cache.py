# Copyright 2024 The Wazo Authors (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from threading import Lock
from time import monotonic_ns
from typing import TYPE_CHECKING, TypedDict

from requests import HTTPError, RequestException

from wazo_calld.plugin_helpers.exceptions import WazoConfdUnreachable

from .dataclasses_ import ConfdParkingLot
from .exceptions import NoSuchParking

if TYPE_CHECKING:
    from wazo_confd_client import Client as ConfdClient

    from wazo_calld.bus import CoreBusConsumer as BusConsumer


logger = logging.getLogger(__name__)


def to_nsec(seconds: int) -> int:
    return seconds * 1_000_000_000


class _ParkinglotEventPayload(TypedDict, total=False):
    id: int


class _TTLEntry:
    hits: int
    expiration: int

    def __init__(self, ttl: int = 10):
        self.hits = 0
        self.expiration = monotonic_ns() + to_nsec(ttl)

    def refresh(self, ttl: int = 10):
        self.hits += 1
        self.expiration = monotonic_ns() + to_nsec(ttl)
        return self


class ParkingLotCache:
    def __init__(self, bus: BusConsumer, confd: ConfdClient):
        self._cache: dict[int, ConfdParkingLot] = {}
        self._invalid_ids: dict[int, _TTLEntry] = {}
        self._confd = confd
        self._lock = Lock()
        self._subscribe(bus)

    def __getitem__(self, parking_id: int) -> ConfdParkingLot:
        self.evict_expired()

        if parking_id in self._invalid_ids:
            with self._lock:
                self._invalid_ids[parking_id].refresh()
            raise NoSuchParking(parking_id)

        if parking_id not in self._cache:
            try:
                return self._fetch_parking_lot(parking_id)
            except Exception:
                with self._lock:
                    self._invalid_ids[parking_id] = _TTLEntry(10)
                raise

        return self._cache[parking_id]

    def evict_expired(self):
        now = monotonic_ns()
        for index in list(self._invalid_ids.keys()):
            if now >= self._invalid_ids[index].expiration:
                logger.debug('evicted expired id from cache: %d', index)
                with self._lock:
                    del self._invalid_ids[index]

    def invalidate(self, key: int) -> None:
        logger.debug('invalidating parking: %s', key)
        with self._lock:
            self._invalid_ids.pop(key, None)
            self._cache.pop(key, None)

    def _fetch_parking_lot(self, parking_id: int) -> ConfdParkingLot:
        logger.debug('fetching parking_lot from confd: %d', parking_id)
        try:
            result = self._confd.parking_lots.get(parking_id)
        except HTTPError as e:
            if e.response.status_code == 404:
                raise NoSuchParking(parking_id)
            raise
        except RequestException as e:
            raise WazoConfdUnreachable(self._confd, e)
        else:
            parking = ConfdParkingLot.from_dict(result)
            with self._lock:
                self._cache[parking.id] = parking

            return parking

    def _on_parking_created(self, payload: _ParkinglotEventPayload) -> None:
        self.invalidate(payload['id'])

    def _on_parking_updated(self, payload: _ParkinglotEventPayload) -> None:
        self.invalidate(payload['id'])

    def _on_parking_deleted(self, payload: _ParkinglotEventPayload) -> None:
        self.invalidate(payload['id'])

    def _subscribe(self, bus: BusConsumer) -> None:
        bus.subscribe('parking_lot_created', self._on_parking_created)
        bus.subscribe('parking_lot_deleted', self._on_parking_deleted)
        bus.subscribe('parking_lot_updated', self._on_parking_updated)
