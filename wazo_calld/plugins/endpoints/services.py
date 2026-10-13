# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import copy
import logging
import random
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone

from wazo_calld.plugin_helpers.exceptions import CalldUninitializedError

logger = logging.getLogger(__name__)


class Endpoint:
    def __init__(self, techno, name, registered, channel_ids):
        self.techno = techno
        self.name = name
        self.registered = registered
        self._channel_ids = set(channel_ids)

    def add_call(self, channel_id):
        self._channel_ids.add(channel_id)

    def remove_call(self, channel_id):
        self._channel_ids.discard(channel_id)

    @property
    def current_call_count(self):
        return len(self._channel_ids)

    def __eq__(self, other):
        return (
            self.techno == other.techno
            and self.name == other.name
            and self.registered == other.registered
            and self.current_call_count == other.current_call_count
        )

    def __repr__(self):
        return '{}({})'.format(
            self.__class__.__name__,
            ', '.join(
                map(
                    str,
                    [self.techno, self.name, self.registered, list(self._channel_ids)],
                )
            ),
        )

    @classmethod
    def from_ari_endpoint_list(cls, endpoint):
        name = endpoint['resource']
        techno = endpoint['technology']
        if endpoint['state'] == 'online':
            registered = True
        elif endpoint['state'] == 'offline':
            registered = False
        else:
            registered = None

        return cls(techno, name, registered, endpoint['channel_ids'])


class StatusCache:
    def __init__(self, ari, endpoints=None):
        self._ari = ari
        self._endpoints = endpoints or {}

    def add_endpoint(self, endpoint):
        if endpoint.techno not in self._endpoints:
            self._endpoints.setdefault(endpoint.techno, {})

        self._endpoints[endpoint.techno][endpoint.name] = endpoint

    def add_new_sip_endpoint(self, endpoint_name):
        if self._endpoints is None:
            raise CalldUninitializedError()

        # endpoint is unlikely to exist in ARI yet, so create it as unregistered
        self.add_endpoint(Endpoint('PJSIP', endpoint_name, False, []))

    def add_new_iax_endpoint(self, endpoint_name):
        if self._endpoints is None:
            raise CalldUninitializedError()

        # endpoint is unlikely to exist in ARI yet, so create it as unregistered
        self.add_endpoint(Endpoint('IAX2', endpoint_name, False, []))

    def get(self, techno, name):
        if self._endpoints is None:
            raise CalldUninitializedError()

        return self._endpoints.get(techno, {}).get(name)

    def pop(self, techno, name):
        if self._endpoints is None:
            raise CalldUninitializedError()

        return self._endpoints.get(techno, {}).pop(name, None)

    def initialize(self):
        logger.debug('initializing endpoint status...')
        for endpoint in self._ari.endpoints.list():
            endpoint_obj = Endpoint.from_ari_endpoint_list(endpoint.json)
            self.add_endpoint(endpoint_obj)
        logger.info(
            'Endpoint cache initialized - %s',
            ','.join(
                [
                    f'{name}: {len(endpoints)}'
                    for name, endpoints in self._endpoints.items()
                ]
            ),
        )


class NotifyingStatusCache(StatusCache):
    def __init__(self, notify_fn, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._notify_fn = notify_fn
        # the bus thread and the endpoint cache builder (replaying held
        # registrations) both update endpoints
        self._lock = threading.Lock()

    @contextmanager
    def update(self, techno, name):
        with self._lock:
            endpoint = self.get(techno, name)
            before = copy.deepcopy(endpoint)
            try:
                yield endpoint
            except Exception:
                if endpoint:
                    raise
                logger.info(
                    'updating an endpoint that is not tracked %s %s', techno, name
                )
                return
            if endpoint == before:
                return
            snapshot = copy.deepcopy(endpoint)
        # notified outside the lock, with a copy the other thread cannot change
        self._notify_fn(snapshot)


# Paging of the background build (factory spec 073). Constants until a stack needs tuning.
PAGE_LIMIT = 100
PAGE_STEP = 90  # a 10-item overlap: up to 10 deletions between two pages lose nothing
PAGE_PAUSE = 0.2  # seconds between two requests, so the build never monopolises confd
RETRY_FIRST = 1.0
RETRY_CAP = 60.0
RETRY_JITTER = 0.2
PROGRESS_EVERY = 10  # pages between two progress lines


def _log(level, **fields):
    # key=value only: counts, durations, error class and status; never a token,
    # a URL or a payload
    logger.log(
        level,
        'endpoint_cache %s',
        ' '.join(f'{key}={value}' for key, value in fields.items()),
    )


def _iso(timestamp):
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def _error_label(exc):
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    return type(exc).__name__, status


class ConfdCache:
    """Line and trunk indexes, loaded once in the background by small paced pages.

    Lookups read the indexes only and never call confd: they run on the bus
    thread, which processes every event in turn. Until an index is ready, the
    status notifications and registrations it would resolve are held (latest
    per endpoint) and replayed by the ready callbacks.
    """

    _asterisk_to_confd_techno_map = {
        'PJSIP': 'sip',
        'IAX2': 'iax',
        'SCCP': 'sccp',
    }

    def __init__(
        self, confd_client, clock=time.time, sleep=time.sleep, jitter=random.uniform
    ):
        self._confd = confd_client
        self._clock = clock
        self._sleep = sleep
        self._jitter = jitter
        # one short lock around index mutations, iterations and the holds; never
        # held across a confd request or a publish
        self.lock = threading.RLock()
        self._trunks = {}
        self._lines = {}
        self._ready = {'trunks': False, 'lines': False}
        # ids touched by a bus event during the build, and ids seen in a page
        self._touched: dict[str, set[int]] = {'trunks': set(), 'lines': set()}
        self._seen: dict[str, set[int]] = {'trunks': set(), 'lines': set()}
        self._total = {'trunks': None, 'lines': None}
        self._ready_callbacks = []
        self._thread = None
        self._state = 'waiting_token'
        self._pages = 0
        self._skipped = 0
        self._retries = 0
        self._failures = 0
        self._last_error = None
        self._last_error_at = None
        self._started_at = None
        self._ready_at = None
        self.held_endpoints = {}
        self.held_registry = {}

    @property
    def trunks_ready(self):
        return self._ready['trunks']

    @property
    def lines_ready(self):
        return self._ready['lines']

    @property
    def ready(self):
        return self._ready['trunks'] and self._ready['lines']

    def on_ready(self, callback):
        """`callback(kind)` runs on the builder thread when 'trunks', then 'lines', is ready."""
        self._ready_callbacks.append(callback)

    def start(self, token=None):
        with self.lock:
            if self._thread:
                return
            self._thread = threading.Thread(
                target=self.build, name='endpoint_cache', daemon=True
            )
            self._thread.start()

    def build(self):
        self._started_at = self._clock()
        self._load('trunks', self._confd.trunks, self._merge_trunk)
        self._load('lines', self._confd.lines, self._merge_line)
        with self.lock:
            self._state = 'ready'
            self._ready_at = self._clock()
        _log(
            logging.INFO,
            state='ready',
            lines=len(self._seen['lines']),
            trunks=len(self._seen['trunks']),
            seconds=f'{self._ready_at - self._started_at:.1f}',
            pages=self._pages,
            retries=self._retries,
        )

    def _load(self, kind, resource, merge):
        with self.lock:
            self._state = f'loading_{kind}'
        offset = 0
        while True:
            items, total = self._fetch(kind, resource, offset)
            with self.lock:
                self._total[kind] = total
                self._pages += 1
                for item in items:
                    try:
                        merge(item)
                    except Exception:
                        self._skipped += 1
                        _log(
                            logging.WARNING,
                            state=self._state,
                            event='skipped_item',
                            skipped_items=self._skipped,
                        )
            if self._pages % PROGRESS_EVERY == 0:
                _log(
                    logging.INFO,
                    state=self._state,
                    pages=self._pages,
                    **{
                        f'{kind}_loaded': len(self._seen[kind]),
                        f'{kind}_total': total,
                    },
                )
            offset += PAGE_STEP
            # A short page (empty included) is the last one: confd honours
            # `limit`. It also ends the load when `offset >= total` would, a
            # full page meaning total >= offset + 100. `total` is only shown in
            # /status: the integration tests' confd mock omits it.
            if len(items) < PAGE_LIMIT:
                break

        with self.lock:
            self._ready[kind] = True
        for callback in self._ready_callbacks:
            try:
                callback(kind)
            except Exception:
                logger.exception('endpoint_cache event=ready_callback_failed')

    def _fetch(self, kind, resource, offset):
        if self._pages:
            self._sleep(PAGE_PAUSE)
        while True:
            try:
                page = resource.list(recurse=True, limit=PAGE_LIMIT, offset=offset)
                items, total = page['items'], page.get('total')
                if not isinstance(items, list) or not isinstance(
                    total, (int, type(None))
                ):
                    raise TypeError('unexpected page shape')
            except Exception as e:
                self._sleep(self._failed(offset, e))
                continue
            with self.lock:
                self._failures = 0
            return items, total

    def _failed(self, offset, exc):
        name, status = _error_label(exc)
        with self.lock:
            self._failures += 1
            self._retries += 1
            self._last_error = name if status is None else f'{name} {status}'
            self._last_error_at = self._clock()
            failures = self._failures
        # the exponent is bounded so a confd down for days never overflows
        backoff = RETRY_FIRST * 2 ** min(failures - 1, 10)
        jitter = self._jitter(1 - RETRY_JITTER, 1 + RETRY_JITTER)
        delay = min(RETRY_CAP, backoff * jitter)
        _log(
            logging.WARNING,
            state=self._state,
            event='retry',
            offset=offset,
            error=name,
            status=status,
            consecutive_failures=failures,
            retry_in=f'{delay:.1f}',
        )
        return delay

    def status(self):
        with self.lock:
            started, ready_at = self._started_at, self._ready_at
            return {
                'state': self._state,
                'trunks_loaded': len(self._seen['trunks']),
                'trunks_total': self._total['trunks'],
                'lines_loaded': len(self._seen['lines']),
                'lines_total': self._total['lines'],
                'pages': self._pages,
                'skipped_items': self._skipped,
                'retries': self._retries,
                'consecutive_failures': self._failures,
                'last_error': self._last_error,
                'last_error_at': _iso(self._last_error_at),
                'held_notifications': len(self.held_endpoints)
                + len(self.held_registry),
                'started_at': _iso(started),
                'ready_at': _iso(ready_at),
                'build_seconds': None
                if ready_at is None
                else round(ready_at - started, 1),
            }

    def _merge_line(self, line):
        techno, name, line_id = line['protocol'], line['name'], line['id']
        value = {
            'id': line_id,
            'technology': techno,
            'name': name,
            'tenant_uuid': line['tenant_uuid'],
        }
        if line_id in self._seen['lines']:
            return  # page overlap
        self._seen['lines'].add(line_id)
        if line_id in self._touched['lines']:
            return  # a bus event already said what this line is
        self._lines.setdefault(techno, {'name': {}, 'username': {}})
        self._lines[techno]['name'][name] = value

    def _merge_trunk(self, trunk):
        if trunk.get('endpoint_sip'):
            techno = 'sip'
            name = trunk['endpoint_sip']['name']
            for key, value in trunk['endpoint_sip']['registration_section_options']:
                if key == 'client_uri':
                    username = value
                    break
            else:
                username = None
        elif trunk.get('endpoint_iax'):
            techno = 'iax'
            name = trunk['endpoint_iax']['name']
            username = name
        elif trunk.get('endpoint_custom'):
            techno = 'custom'
            name = trunk['endpoint_custom']['interface']
            username = name
        else:
            self._seen['trunks'].add(trunk['id'])
            return  # a trunk with no endpoint has no status to track

        trunk_id = trunk['id']
        value = {
            'id': trunk_id,
            'technology': techno,
            'name': name,
            'tenant_uuid': trunk['tenant_uuid'],
        }
        if trunk_id in self._seen['trunks']:
            return
        self._seen['trunks'].add(trunk_id)
        if trunk_id in self._touched['trunks']:
            return
        self._index_trunk(techno, trunk_id, name, username, value)

    def _index_trunk(self, techno, trunk_id, name, username, value):
        self._trunks.setdefault(techno, {'id': {}, 'name': {}, 'username': {}})
        self._trunks[techno]['name'][name] = value
        self._trunks[techno]['id'][trunk_id] = value
        if username:
            self._trunks[techno]['username'][username] = value

    def _touch(self, kind, item_id):
        if not self._ready[kind]:
            self._touched[kind].add(item_id)

    def add_line(self, techno, line_id, name, username, tenant_uuid):
        value = {
            'id': line_id,
            'technology': techno,
            'name': name,
            'tenant_uuid': tenant_uuid,
        }
        with self.lock:
            self._touch('lines', line_id)
            self._lines.setdefault(techno, {'name': {}, 'username': {}})
            self._lines[techno]['name'][name] = value
            if username:
                self._lines[techno]['username'][username] = value

    def add_trunk(self, techno, trunk_id, name, username, tenant_uuid):
        value = {
            'id': trunk_id,
            'technology': techno,
            'name': name,
            'tenant_uuid': tenant_uuid,
        }
        with self.lock:
            self._touch('trunks', trunk_id)
            self._index_trunk(techno, trunk_id, name, username, value)

    def delete_line(self, line_id):
        with self.lock:
            self._touch('lines', line_id)
            self._delete(self._lines, line_id)

    def delete_trunk(self, trunk_id):
        with self.lock:
            self._touch('trunks', trunk_id)
            self._delete(self._trunks, trunk_id)

    @staticmethod
    def _delete(endpoints, item_id):
        to_remove = []
        for techno, indexes in endpoints.items():
            for index, items in indexes.items():
                for identifier, item in items.items():
                    if item['id'] == item_id:
                        to_remove.append((techno, index, identifier))

        for techno, index, identifier in to_remove:
            del endpoints[techno][index][identifier]

    def get_line(self, techno, name):
        return self._get_endpoint_by_index(techno, name, self._lines, index='name')

    def get_trunk(self, techno, name):
        return self._get_endpoint_by_index(techno, name, self._trunks, index='name')

    def get_trunk_by_id(self, trunk_id):
        with self.lock:
            for indexes in self._trunks.values():
                if trunk := indexes['id'].get(trunk_id):
                    return trunk
        return None

    def get_trunk_by_username(self, techno, username):
        return self._get_endpoint_by_index(
            techno, username, self._trunks, index='username'
        )

    def list_lines(self, tenant_uuid):
        return self._list('lines', self._lines, tenant_uuid)

    def list_trunks(self, tenant_uuid):
        return self._list('trunks', self._trunks, tenant_uuid)

    def _list(self, kind, endpoints, tenant_uuid):
        with self.lock:
            if not self._ready[kind]:
                raise CalldUninitializedError()
            return [
                item
                for indexes in endpoints.values()
                for item in indexes['name'].values()
                if item['tenant_uuid'] == tenant_uuid
            ]

    def update_line(self, techno, line_id, name, username, tenant_uuid):
        with self.lock:
            self.delete_line(line_id)
            self.add_line(techno, line_id, name, username, tenant_uuid)

    def update_trunk(self, techno, trunk_id, name, username, tenant_uuid):
        with self.lock:
            self.delete_trunk(trunk_id)
            self.add_trunk(techno, trunk_id, name, username, tenant_uuid)

    def _get_endpoint_by_index(self, techno, value, endpoints, index):
        confd_techno = self._asterisk_to_confd_techno_map.get(techno, techno)
        with self.lock:
            return endpoints.get(confd_techno, {}).get(index, {}).get(value)


class EndpointsService:
    _techno_map = {
        'sip': 'PJSIP',
        'iax': 'IAX2',
    }

    def __init__(self, confd_cache, status_cache):
        self._confd = confd_cache
        self.status_cache = status_cache

    def list_lines(self, tenant_uuid):
        confd_endpoints = self._confd.list_lines(tenant_uuid)
        return self._list_endpoints(confd_endpoints)

    def list_trunks(self, tenant_uuid):
        confd_endpoints = self._confd.list_trunks(tenant_uuid)
        return self._list_endpoints(confd_endpoints)

    def _list_endpoints(self, confd_endpoints):
        results = []
        for confd_endpoint in confd_endpoints:
            endpoint = dict(confd_endpoint)
            ast_techno = self._techno_map.get(
                endpoint['technology'], endpoint['technology']
            )
            ast_endpoint = self.status_cache.get(ast_techno, confd_endpoint['name'])
            if ast_endpoint:
                endpoint['registered'] = ast_endpoint.registered
                endpoint['current_call_count'] = ast_endpoint.current_call_count
            results.append(endpoint)

        count = len(results)
        return results, count, count
