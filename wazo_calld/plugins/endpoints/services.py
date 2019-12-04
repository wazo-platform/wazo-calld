# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import copy
import threading
from contextlib import contextmanager

from requests import HTTPError

from wazo_calld.exceptions import CalldUninitializedError, WazoConfdError

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
            ', '.join(map(str, [self.techno, self.name, self.registered, list(self._channel_ids)])),
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

        if not self._endpoints:
            self._initialize()

    def add_endpoint(self, endpoint):
        if endpoint.techno not in self._endpoints:
            self._endpoints.setdefault(endpoint.techno, {})

        self._endpoints[endpoint.techno][endpoint.name] = endpoint

    def get(self, techno, name):
        if self._endpoints is None:
            raise CalldUninitializedError()

        return self._endpoints.get(techno, {}).get(name)

    def _initialize(self):
        logger.debug('initializing endpoint status...')
        for endpoint in self._ari.endpoints.list():
            endpoint_obj = Endpoint.from_ari_endpoint_list(endpoint.json)
            self.add_endpoint(endpoint_obj)
        logger.info(
            'Endpoint cache initialized - %s',
            ','.join([
                '{}: {}'.format(name, len(endpoints)) for name, endpoints in self._endpoints.items()
            ]))


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
                logger.info('updating an endpoint that is not tracked %s %s', techno, name)
            else:
                raise
        else:
            if endpoint != before:
                self._notify_fn(endpoint)


class ConfdCache:

    _asterisk_to_confd_techno_map = {
        'PJSIP': 'sip',
        'IAX2': 'iax',
    }

    def __init__(self, confd_client):
        self._confd = confd_client
        self._trunks = {}
        self._initialized = False
        self._initialization_lock = threading.Lock()

    def add_trunk(self, techno, trunk_id, name, username, tenant_uuid):
        value = {'id': trunk_id, 'name': name, 'tenant_uuid': tenant_uuid}
        self._trunks.setdefault(techno, {'name': {}, 'username': {}})
        self._trunks[techno]['name'][name] = value
        if username:
            self._trunks[techno]['username'][username] = value

    def delete_trunk(self, trunk_id):
        to_remove = []

        for techno, items in self._trunks.items():
            for index, items in items.items():
                for identifier, trunk in items.items():
                    if trunk['id'] == trunk_id:
                        to_remove.append((techno, index, identifier))

        for techno, index, identifier in to_remove:
            del self._trunks[techno][index][identifier]

    def update_trunk(self, trunk_id):
        self.delete_trunk(trunk_id)
        self.add_trunk(trunk_id)

    def get_trunk(self, techno, name):
        if not self._initialized:
            self._initialize()

        confd_techno = self._asterisk_to_confd_techno_map.get(techno, techno)
        return self._trunks.get(confd_techno, {'name': {}})['name'].get(name, None)

    def get_trunk_by_username(self, techno, username):
        if not self._initialized:
            self._initialize()

        confd_techno = self._asterisk_to_confd_techno_map.get(techno, techno)
        return self._trunks.get(confd_techno, {'username': {}})['username'].get(username, None)

    def _initialize(self):
        with self._initialization_lock:
            # The initialization migh have happened while we were waiting on the lock
            if self._initialized:
                return

            result = self._confd.trunks.list(recurse=True)
            self._update_trunk_cache(result['items'])

    def _update_trunk_cache(self, trunks):
        for trunk in trunks:
            if trunk.get('endpoint_sip'):
                techno = 'sip'
                name = trunk['endpoint_sip']['name']
                username = trunk['endpoint_sip']['username']
            elif trunk.get('endpoint_iax'):
                techno = 'iax'
                name = trunk['endpoint_iax']['name']
                username = name
            elif trunk.get('endpoint_custom'):
                techno = 'custom'
                name = trunk['endpoint_custom']['interface']
                username = name

            value = {'id': trunk['id'], 'name': name, 'tenant_uuid': trunk['tenant_uuid']}
            self._trunks.setdefault(techno, {'name': {}, 'username': {}})
            self._trunks[techno]['name'][name] = value
            self._trunks[techno]['username'][username] = value

        logger.info(
            'trunk cache updated %s entries',
            sum(len(names) for names in self._trunks.values()),
        )
        self._initialized = True


class EndpointsService:

    _confd_to_asterisk_techno_map = {
        'sip': 'PJSIP',
        'iax': 'IAX2',
    }

    def __init__(self, confd_client, ari, status_cache):
        self._confd = confd_client
        self._ari = ari
        self.status_cache = status_cache

    def list_trunks(self, tenant_uuid, list_params):
        try:
            result = self._confd.trunks.list(tenant_uuid=tenant_uuid, **list_params)
        except HTTPError as e:
            raise WazoConfdError(self._confd, e)
        filtered = result['total']

        try:
            count_result = self._confd.trunks.list(tenant_uuid=tenant_uuid, limit=1)
        except HTTPError as e:
            raise WazoConfdError(self._confd, e)
        total = count_result['total']

        results = []
        for confd_trunk in result['items']:
            trunk = self._build_static_fields(confd_trunk)
            trunk = self._build_dynamic_fields(trunk)
            results.append(trunk)

        return results, total, filtered

    def _build_dynamic_fields(self, trunk):
        techno = trunk.get('technology')
        if techno not in ('sip', 'iax'):
            return trunk

        ast_techno = self._confd_to_asterisk_techno_map.get(techno)
        endpoint = self.status_cache.get(ast_techno, trunk['name'])
        if not endpoint:
            return trunk

        trunk['registered'] = endpoint.registered
        trunk['current_call_count'] = endpoint.current_call_count

        return trunk

    def _build_static_fields(self, confd_trunk):
        trunk = {
            'id': confd_trunk['id'],
            'type': 'trunk',
        }

        if confd_trunk.get('endpoint_sip'):
            trunk['technology'] = 'sip'
            trunk['name'] = confd_trunk['endpoint_sip']['name']
        elif confd_trunk.get('endpoint_iax'):
            trunk['technology'] = 'iax'
            trunk['name'] = confd_trunk['endpoint_iax']['name']
        elif confd_trunk.get('endpoint_custom'):
            trunk['technology'] = 'custom'
            trunk['name'] = confd_trunk['endpoint_custom']['interface']

        return trunk
