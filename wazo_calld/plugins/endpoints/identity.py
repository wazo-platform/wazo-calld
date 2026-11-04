# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Which line or trunk an Asterisk endpoint is, and in which tenant.

Asterisk holds that identity on each PJSIP endpoint (WAZO_LINE_ID or WAZO_TRUNK_ID,
and __WAZO_TENANT_UUID), so an endpoint is read from ARI the first time it is needed,
one at a time, and remembered until a wazo-confd event says it changed. IAX2 and SCCP
endpoints carry no such variables: they are read from wazo-confd by name.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Final, Literal, TypeGuard, Union

from ari.exceptions import ARINotFound
from requests import RequestException
from wazo_amid_client.exceptions import InvalidAmidError

from wazo_calld.exceptions import AsteriskARINotInitialized

logger = logging.getLogger(__name__)

# A failed lookup is not retried for that endpoint before this delay, so that an
# unreachable ARI or wazo-confd does not cost one request per telephony event.
FAILURE_MARK_SECONDS = 30
# Failed lookups are logged once per failure class in this interval, with a count.
FAILURE_LOG_INTERVAL_SECONDS = 60
# A name evicted by a wazo-confd event is not read from ARI before this delay:
# Asterisk reloads its configuration after wazo-confd's event, and a read in
# between would answer the identity the event just removed.
RELOAD_WINDOW_SECONDS = 30

LINE: Final = 'line'
TRUNK: Final = 'trunk'

Kind = Literal['line', 'trunk']
Key = tuple[str, str]


@dataclass(frozen=True)
class EndpointIdentity:
    kind: Kind
    id: int
    tenant_uuid: str


class _Marker:
    pass


# The endpoint exists for Asterisk or wazo-confd but is neither a line nor a trunk
# (a meeting guest, a template, an unknown name).
NOT_A_LINE_OR_TRUNK = _Marker()
# The last lookup failed less than FAILURE_MARK_SECONDS ago, or the name was
# evicted less than RELOAD_WINDOW_SECONDS ago.
RECENTLY_FAILED = _Marker()
# The client URI was absent from the last registration list.
UNKNOWN_URI = _Marker()

Entry = Union[EndpointIdentity, _Marker]

LOOKUP_FAILURES = (RequestException, AsteriskARINotInitialized, InvalidAmidError)


class IdentityMap:
    """The identities known so far, empty at start.

    One lock covers reads and writes, never a request. A lookup reads the map's
    sequence before its request; an eviction of the endpoint's name or of the
    identity's id after that point drops the lookup's answer, so a stale answer
    never outlives the event that evicted it. The eviction stamps are only
    compared with the sequence of a lookup in flight, so they are dropped
    whenever no lookup is in flight.
    """

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._lock = Lock()
        self._entries: dict[Key, Entry] = {}
        self._keys_by_id: dict[tuple[Kind, int], set[Key]] = {}
        # names not read before that time: a failed lookup, or an eviction by id
        self._not_before: dict[Key, float] = {}
        self._sequence = 0
        self._lookups_in_flight = 0
        self._name_evicted_at: dict[Key, int] = {}
        self._id_evicted_at: dict[tuple[Kind, int], int] = {}
        self._client_uris: dict[str, str] = {}
        self._unknown_uris: set[str] = set()
        self._uris_generation = 0
        self._uris_not_before = 0.0

    def lookup(self, key: Key) -> tuple[Entry | None, int]:
        with self._lock:
            return self._lookup(key), self._sequence

    @contextmanager
    def missed(self, key: Key) -> Iterator[tuple[Entry | None, int]]:
        """A lookup that, on a miss, stays in flight until the block ends."""
        with self._lock:
            entry = self._lookup(key)
            generation = self._sequence
            self._lookups_in_flight += entry is None
        try:
            yield entry, generation
        finally:
            if entry is None:
                with self._lock:
                    self._lookups_in_flight -= 1
                    if not self._lookups_in_flight:
                        self._name_evicted_at.clear()
                        self._id_evicted_at.clear()

    def store(self, key: Key, entry: Entry, generation: int) -> bool:
        with self._lock:
            if self._evicted_since(key, entry, generation):
                return False
            self._remove(key)
            self._entries[key] = entry
            if isinstance(entry, EndpointIdentity):
                self._keys_by_id.setdefault((entry.kind, entry.id), set()).add(key)
            return True

    def mark_failed(self, key: Key) -> None:
        # an event that wrote the name meanwhile wins: an entry is read before a mark
        with self._lock:
            self._not_before[key] = self._clock() + FAILURE_MARK_SECONDS

    def write(self, key: Key, identity: EndpointIdentity) -> None:
        with self._lock:
            self._evict_id(identity.kind, identity.id)
            self._evict_name(key)
            self._entries[key] = identity
            self._keys_by_id.setdefault((identity.kind, identity.id), set()).add(key)

    def evict(self, kind: Kind, id_: int) -> list[Key]:
        with self._lock:
            return self._evict_id(kind, id_)

    def client_uri_endpoint(self, uri: str) -> tuple[str | _Marker | None, int]:
        with self._lock:
            if uri in self._unknown_uris:
                return UNKNOWN_URI, self._uris_generation
            if self._clock() < self._uris_not_before:
                return RECENTLY_FAILED, self._uris_generation
            return self._client_uris.get(uri), self._uris_generation

    def replace_client_uris(
        self, endpoints_by_uri: dict[str, str], asked: str, generation: int
    ) -> None:
        with self._lock:
            if generation != self._uris_generation:
                return
            self._client_uris = dict(endpoints_by_uri)
            if asked not in endpoints_by_uri:
                self._unknown_uris.add(asked)

    def mark_client_uris_failed(self, generation: int) -> None:
        with self._lock:
            if generation == self._uris_generation:
                self._uris_not_before = self._clock() + FAILURE_MARK_SECONDS

    def forget_client_uris(self) -> None:
        with self._lock:
            self._client_uris = {}
            self._unknown_uris = set()
            self._uris_generation += 1
            self._uris_not_before = 0.0

    def _lookup(self, key: Key) -> Entry | None:
        entry = self._entries.get(key)
        if entry is None and key in self._not_before:
            if self._clock() < self._not_before[key]:
                return RECENTLY_FAILED
            del self._not_before[key]
        return entry

    def _evicted_since(self, key: Key, entry: Entry | None, generation: int) -> bool:
        if self._name_evicted_at.get(key, 0) > generation:
            return True
        if isinstance(entry, EndpointIdentity):
            return self._id_evicted_at.get((entry.kind, entry.id), 0) > generation
        return False

    def _evict_id(self, kind: Kind, id_: int) -> list[Key]:
        self._sequence += 1
        self._id_evicted_at[(kind, id_)] = self._sequence
        keys = self._keys_by_id.pop((kind, id_), set())
        for key in keys:
            self._entries.pop(key, None)
            self._name_evicted_at[key] = self._sequence
            self._not_before[key] = self._clock() + RELOAD_WINDOW_SECONDS
        return list(keys)

    def _evict_name(self, key: Key) -> None:
        self._sequence += 1
        self._name_evicted_at[key] = self._sequence
        self._remove(key)

    def _remove(self, key: Key) -> None:
        previous = self._entries.pop(key, None)
        if isinstance(previous, EndpointIdentity):
            id_key = (previous.kind, previous.id)
            keys = self._keys_by_id.get(id_key, set())
            keys.discard(key)
            if not keys:
                self._keys_by_id.pop(id_key, None)


class _FailureLog:
    """One warning per failure class per interval, counting the failures since the last one."""

    def __init__(self, clock: Callable[[], float]):
        self._clock = clock
        self._last_warning: dict[tuple, float] = {}
        self._unlogged: dict[tuple, int] = {}

    def failed(self, source: str, error: Exception, name: str) -> None:
        status = _http_status(error)
        failure_class = (source, type(error).__name__, status)
        logger.debug(
            'endpoint identity lookup failed: source=%s endpoint=%s error=%s',
            source,
            name,
            error,
        )
        count = self._unlogged.get(failure_class, 0) + 1
        now = self._clock()
        last = self._last_warning.get(failure_class)
        if last is not None and now - last < FAILURE_LOG_INTERVAL_SECONDS:
            self._unlogged[failure_class] = count
            return
        self._last_warning[failure_class] = now
        self._unlogged[failure_class] = 0
        logger.warning(
            'endpoint identity lookups failed: source=%s count=%d error=%s status=%s',
            source,
            count,
            type(error).__name__,
            status,
        )


def _http_status(error: Exception) -> int | None:
    original = getattr(error, 'original_error', error)
    response = getattr(original, 'response', None)
    return getattr(response, 'status_code', None)


class EndpointIdentities:
    """Answers which line or trunk an endpoint is, from the map, else by one request."""

    def __init__(
        self,
        identity_map: IdentityMap,
        ari_client,
        confd_client,
        amid_client,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._map = identity_map
        self._ari = ari_client
        self._confd = confd_client
        self._amid = amid_client
        self._failures = _FailureLog(clock)
        self._readers: dict[str, tuple[str, Callable[[str], Entry]]] = {
            'PJSIP': ('ARI', self._read_pjsip),
            'IAX2': ('wazo-confd IAX', self._read_iax),
            'SCCP': ('wazo-confd SCCP', self._read_sccp),
        }

    def identity_of(self, techno: str, name: str) -> EndpointIdentity | None:
        if techno not in self._readers:
            return None
        key = (techno, name)
        with self._map.missed(key) as (entry, generation):
            if entry is None:
                source, read = self._readers[techno]
                try:
                    entry = read(name)
                except LOOKUP_FAILURES as e:
                    self._failures.failed(source, e, name)
                    self._map.mark_failed(key)
                    return None
                self._map.store(key, entry, generation)
        return entry if isinstance(entry, EndpointIdentity) else None

    def endpoint_of_client_uri(self, uri: str) -> str | None:
        name, generation = self._map.client_uri_endpoint(uri)
        if isinstance(name, _Marker):
            return None
        if name is not None:
            return name

        started = time.monotonic()
        try:
            registrations = self._amid.action('PJSIPShowRegistrationsOutbound')
        except LOOKUP_FAILURES as e:
            self._failures.failed('wazo-amid', e, uri)
            self._map.mark_client_uris_failed(generation)
            return None
        # a registration configured without an endpoint names none
        endpoints_by_uri = {
            registration['ClientUri']: registration['Endpoint']
            for registration in registrations
            if registration.get('Event') == 'OutboundRegistrationDetail'
            and registration.get('Endpoint')
        }
        self._map.replace_client_uris(endpoints_by_uri, uri, generation)
        logger.info(
            'outbound registrations read: client_uris=%d duration=%.3fs',
            len(endpoints_by_uri),
            time.monotonic() - started,
        )
        return endpoints_by_uri.get(uri)

    def _read_pjsip(self, name: str) -> Entry:
        try:
            tuples = self._ari.asterisk.getObject(
                configClass='res_pjsip', objectType='endpoint', id=name
            )
        except ARINotFound:
            return NOT_A_LINE_OR_TRUNK
        attributes = {item['attribute']: item['value'] for item in tuples}
        line_id = attributes.get('WAZO_LINE_ID')
        trunk_id = attributes.get('WAZO_TRUNK_ID')
        tenant_uuid = attributes.get('__WAZO_TENANT_UUID')
        if line_id is None and trunk_id is None:
            return NOT_A_LINE_OR_TRUNK
        if _is_id(line_id) and trunk_id is None and tenant_uuid:
            return EndpointIdentity(LINE, int(line_id), tenant_uuid)
        if _is_id(trunk_id) and line_id is None and tenant_uuid:
            return EndpointIdentity(TRUNK, int(trunk_id), tenant_uuid)
        logger.error(
            'inconsistent endpoint identity: endpoint=%s line_id=%s trunk_id=%s tenant_uuid=%s',
            name,
            line_id,
            trunk_id,
            tenant_uuid,
        )
        return NOT_A_LINE_OR_TRUNK

    def _read_iax(self, name: str) -> Entry:
        endpoints = self._confd.endpoints_iax.list(name=name, recurse=True)['items']
        for endpoint in endpoints:
            trunk = endpoint.get('trunk')
            if trunk and endpoint.get('tenant_uuid'):
                return EndpointIdentity(TRUNK, trunk['id'], endpoint['tenant_uuid'])
        return NOT_A_LINE_OR_TRUNK

    def _read_sccp(self, name: str) -> Entry:
        lines = self._confd.lines.list(name=name, recurse=True)['items']
        for line in lines:
            if line.get('protocol') == 'sccp' and line.get('tenant_uuid'):
                return EndpointIdentity(LINE, line['id'], line['tenant_uuid'])
        return NOT_A_LINE_OR_TRUNK


def _is_id(value: str | None) -> TypeGuard[str]:
    return value is not None and value.isdigit()
