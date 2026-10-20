# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import copy
import logging
import threading
import time
from collections.abc import Hashable
from contextlib import contextmanager

import tenacity

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

    @contextmanager
    def update(self, techno, name):
        endpoint = self.get(techno, name)
        before = copy.deepcopy(endpoint)
        try:
            yield endpoint
        except Exception:
            if not endpoint:
                logger.info(
                    'updating an endpoint that is not tracked %s %s', techno, name
                )
            else:
                raise
        else:
            if endpoint != before:
                self._notify_fn(endpoint)


# Constants until a stack needs tuning
PAGE_LIMIT = 100
PAGE_STEP = 90  # a 10-item overlap: up to 10 deletions between two pages lose nothing
PAGE_PAUSE = 0.2  # seconds after each request, so a load never monopolises confd
RETRY_MAX = 60  # seconds, the widest wait between two attempts of one request
PROGRESS_EVERY = 10  # pages between two progress lines


def _log(level, **fields):
    # key=value only: counts, durations, error class and status; never a token,
    # a URL or a payload
    logger.log(
        level,
        'endpoint_cache %s',
        ' '.join(f'{key}={value}' for key, value in fields.items()),
    )


def _log_retry(offset):
    def before_sleep(retry_state):
        exc = retry_state.outcome.exception()
        response = getattr(exc, 'response', None)
        _log(
            logging.WARNING,
            event='retry',
            offset=offset,
            error=type(exc).__name__,
            status=getattr(response, 'status_code', None),
            attempt=retry_state.attempt_number,
            retry_in=f'{retry_state.next_action.sleep:.1f}',
        )

    return before_sleep


def _get_page(list_fn, offset, sleep):
    def get():
        page = list_fn(limit=PAGE_LIMIT, offset=offset)
        items, total = page['items'], page.get('total')
        if not isinstance(items, list) or not isinstance(total, (int, type(None))):
            raise TypeError('unexpected page shape')
        return items, total

    # every failure is retried, the same request, forever: a background load
    # has nothing better to do than wait for confd
    retrying = tenacity.Retrying(
        wait=tenacity.wait_random_exponential(multiplier=1, max=RETRY_MAX),
        sleep=sleep,
        before_sleep=_log_retry(offset),
    )
    return retrying(get)


def pages(list_fn, on_page, sleep=time.sleep):
    """Yield every item of a confd collection, one small page at a time.

    `list_fn(limit=, offset=)` returns a confd page; `on_page(total)` runs once
    each page is consumed. Pages overlap so that a deletion between two
    requests skips no item; an item seen in the overlap is yielded once.
    """
    offset = 0
    seen = set()
    while True:
        items, total = _get_page(list_fn, offset, sleep)
        sleep(PAGE_PAUSE)
        for item in items:
            item_id = item.get('id') if isinstance(item, dict) else None
            # an unhashable id is yielded as is: the merge skips and counts it
            if item_id is not None and isinstance(item_id, Hashable):
                if item_id in seen:
                    continue
                seen.add(item_id)
            yield item
        on_page(total)
        offset += PAGE_STEP
        # A short page (empty included) is the last one, confd honouring
        # `limit`; `total` ends the load if it does not.
        if len(items) < PAGE_LIMIT or (total is not None and offset >= total):
            return


class ConfdCache:
    """Line and trunk indexes, loaded once in the background.

    Lookups read the indexes only and never call confd: they run on the bus
    thread, which processes every event in turn. An index that is not loaded
    yet resolves nothing.
    """

    _asterisk_to_confd_techno_map = {
        'PJSIP': 'sip',
        'IAX2': 'iax',
        'SCCP': 'sccp',
    }

    def __init__(self, confd_client, sleep=time.sleep, monotonic=time.monotonic):
        self._confd = confd_client
        self._sleep = sleep
        self._monotonic = monotonic
        # one short lock around index mutations and iterations; never held
        # across a confd request or a publish
        self._lock = threading.RLock()
        self._trunks = {}
        self._lines = {}
        self._ready = {'trunks': False, 'lines': False}
        # ids changed by a bus event while their kind loads: a later page is
        # older than the event and must not overwrite or resurrect them
        self._touched: dict[str, set[int]] = {'trunks': set(), 'lines': set()}
        self._loaded = {'trunks': 0, 'lines': 0}
        self._pages = 0
        self._skipped = 0
        self._thread = None

    @property
    def ready(self):
        return self._ready['trunks'] and self._ready['lines']

    def start(self, token=None):
        with self._lock:
            if self._thread:
                return
            self._thread = threading.Thread(
                target=self.build, name='endpoint_cache', daemon=True
            )
        self._thread.start()

    def build(self):
        started = self._monotonic()
        self._load('trunks', self._confd.trunks, self._merge_trunk)
        self._load('lines', self._confd.lines, self._merge_line)
        _log(
            logging.INFO,
            state='ready',
            lines=self._loaded['lines'],
            trunks=self._loaded['trunks'],
            seconds=round(self._monotonic() - started, 1),
            pages=self._pages,
        )

    def _load(self, kind, resource, merge):
        def list_fn(**paging):
            return resource.list(recurse=True, **paging)

        def on_page(total):
            self._pages += 1
            if self._pages % PROGRESS_EVERY == 0:
                _log(
                    logging.INFO,
                    state=f'loading_{kind}',
                    pages=self._pages,
                    loaded=self._loaded[kind],
                    total=total,
                )

        for item in pages(list_fn, on_page, self._sleep):
            with self._lock:
                try:
                    merge(item)
                except Exception:
                    self._skipped += 1
                    _log(logging.WARNING, event='skipped_item', skipped=self._skipped)
                    continue
                self._loaded[kind] += 1

        with self._lock:
            self._ready[kind] = True
            self._touched[kind] = set()

    def _merge_line(self, line):
        line_id = line['id']
        techno = line['protocol']
        value = {
            'id': line_id,
            'technology': techno,
            'name': line['name'],
            'tenant_uuid': line['tenant_uuid'],
        }
        if line_id in self._touched['lines']:
            return
        self._lines.setdefault(techno, {'name': {}, 'username': {}})
        self._lines[techno]['name'][value['name']] = value

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
            logger.info(
                'ignoring trunk %s which is not associated to an endpoint',
                trunk['id'],
            )
            return

        trunk_id = trunk['id']
        tenant_uuid = trunk['tenant_uuid']
        if trunk_id in self._touched['trunks']:
            return
        self._add_trunk(techno, trunk_id, name, username, tenant_uuid)

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
        with self._lock:
            self._touch('lines', line_id)
            self._lines.setdefault(techno, {'name': {}, 'username': {}})
            self._lines[techno]['name'][name] = value
            if username:
                self._lines[techno]['username'][username] = value

    def add_trunk(self, techno, trunk_id, name, username, tenant_uuid):
        with self._lock:
            self._touch('trunks', trunk_id)
            self._add_trunk(techno, trunk_id, name, username, tenant_uuid)

    def _add_trunk(self, techno, trunk_id, name, username, tenant_uuid):
        value = {
            'id': trunk_id,
            'technology': techno,
            'name': name,
            'tenant_uuid': tenant_uuid,
        }
        self._trunks.setdefault(techno, {'id': {}, 'name': {}, 'username': {}})
        self._trunks[techno]['name'][name] = value
        self._trunks[techno]['id'][trunk_id] = value
        if username:
            self._trunks[techno]['username'][username] = value

    def delete_line(self, line_id):
        with self._lock:
            self._touch('lines', line_id)
            self._delete(self._lines, line_id)

    def delete_trunk(self, trunk_id):
        with self._lock:
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
        with self._lock:
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
        with self._lock:
            if not self._ready[kind]:
                raise CalldUninitializedError()
            return [
                item
                for indexes in endpoints.values()
                for item in indexes['name'].values()
                if item['tenant_uuid'] == tenant_uuid
            ]

    def update_line(self, techno, line_id, name, username, tenant_uuid):
        with self._lock:
            self.delete_line(line_id)
            self.add_line(techno, line_id, name, username, tenant_uuid)

    def update_trunk(self, techno, trunk_id, name, username, tenant_uuid):
        with self._lock:
            self.delete_trunk(trunk_id)
            self.add_trunk(techno, trunk_id, name, username, tenant_uuid)

    def _get_endpoint_by_index(self, techno, value, endpoints, index):
        confd_techno = self._asterisk_to_confd_techno_map.get(techno, techno)
        with self._lock:
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
