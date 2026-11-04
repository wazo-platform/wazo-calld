# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import copy
import logging
from contextlib import contextmanager

from requests import HTTPError, RequestException

from wazo_calld.plugin_helpers.exceptions import (
    CalldUninitializedError,
    WazoConfdUnreachable,
)

from .exceptions import InvalidListParameters

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


class EndpointsService:
    _techno_map = {
        'sip': 'PJSIP',
        'iax': 'IAX2',
    }

    def __init__(self, confd_client, status_cache):
        self._confd = confd_client
        self.status_cache = status_cache

    def list_lines(self, tenant_uuid, **params):
        result = self._list(self._confd.lines, tenant_uuid, params)
        items = [self._line_item(line) for line in result['items']]
        total = self._total(result)
        return self._with_status(items), total, total

    def list_trunks(self, tenant_uuid, **params):
        result = self._list(self._confd.trunks, tenant_uuid, params)
        items = [self._trunk_item(trunk) for trunk in result['items']]
        total = self._total(result)
        return self._with_status(items), total, total

    def _list(self, resource, tenant_uuid, params):
        try:
            return resource.list(tenant_uuid=tenant_uuid, **params)
        except HTTPError as e:
            if e.response is not None and e.response.status_code == 400:
                raise InvalidListParameters(e.response.json())
            raise
        except RequestException as e:
            raise WazoConfdUnreachable(self._confd, e)

    @staticmethod
    def _total(result):
        # wazo-confd counts the items matching the search before paging; a list
        # answered without that count (wazo-confd-mock) is counted as returned
        return result.get('total', len(result['items']))

    @staticmethod
    def _line_item(line):
        return {
            'id': line['id'],
            'technology': line['protocol'],
            'name': line['name'],
            'tenant_uuid': line['tenant_uuid'],
        }

    @staticmethod
    def _trunk_item(trunk):
        item = {'id': trunk['id'], 'name': None, 'tenant_uuid': trunk['tenant_uuid']}
        if trunk.get('endpoint_sip'):
            item.update(technology='sip', name=trunk['endpoint_sip']['name'])
        elif trunk.get('endpoint_iax'):
            item.update(technology='iax', name=trunk['endpoint_iax']['name'])
        elif trunk.get('endpoint_custom'):
            item.update(technology='custom', name=trunk['endpoint_custom']['interface'])
        return item

    def _with_status(self, items):
        for item in items:
            if 'technology' not in item:
                continue
            ast_techno = self._techno_map.get(item['technology'], item['technology'])
            ast_endpoint = self.status_cache.get(ast_techno, item['name'])
            if ast_endpoint:
                item['registered'] = ast_endpoint.registered
                item['current_call_count'] = ast_endpoint.current_call_count
        return items
