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

    _confd_to_asterisk_techno_map = {
        'sip': 'PJSIP',
        'iax': 'IAX2',
    }

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

        ast_techno = self._confd_to_asterisk_techno_map.get(techno)
        return self._endpoints.get(ast_techno, {}).get(name)

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

    def _build_dynamic_fields(self, trunk):
        techno = trunk.get('technology')
        if techno not in ('sip', 'iax'):
            return trunk

        endpoint = self.status_cache.get(techno, trunk['name'])
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
