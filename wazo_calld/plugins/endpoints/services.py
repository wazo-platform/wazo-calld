# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from requests import HTTPError

from wazo_calld.exceptions import CalldUninitializedError, WazoConfdError

logger = logging.getLogger(__name__)


class Endpoint:
    def __init__(self, techno, name, registered, current_call_count):
        self.techno = techno
        self.name = name
        self.registered = registered
        self.current_call_count = current_call_count

    def __repr__(self):
        return '{}({})'.format(
            self.__class__.__name__,
            ', '.join(map(str, [self.techno, self.name, self.registered, self.current_call_count])),
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
        current_call_count = len(endpoint['channel_ids'])

        return cls(techno, name, registered, current_call_count)


class StatusCache:

    def __init__(self, ari):
        self._ari = ari
        self._endpoints = {}

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


class EndpointsService:

    _confd_to_asterisk_techno_map = {
        'sip': 'PJSIP',
        'iax': 'IAX2',
    }

    def __init__(self, confd_client, ari):
        self._confd = confd_client
        self._ari = ari
        self.status_cache = StatusCache(self._ari)

    def list_trunks(self, tenant_uuid):
        try:
            result = self._confd.trunks.list(tenant_uuid=tenant_uuid)
        except HTTPError as e:
            raise WazoConfdError(self._confd, e)

        total = filtered = result['total']

        results = []
        for confd_trunk in result['items']:
            trunk = self._build_static_fields(confd_trunk)
            trunk = self._build_dynamic_fields(trunk)
            results.append(trunk)

        return results, total, filtered

    def update_endpoint(self, techno, name, registered=None):
        endpoint = self.status_cache.get(techno, name)
        if not endpoint:
            logger.info('updating an endpoint that is not tracked %s %s', techno, name)
            return

        updated = False

        if endpoint.registered != registered:
            endpoint.registered = registered
            updated = True

        if updated:
            logger.debug('%s has been updated', endpoint)

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
