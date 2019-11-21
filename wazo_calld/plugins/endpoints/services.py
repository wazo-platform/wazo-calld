# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from requests import HTTPError

from wazo_calld.exceptions import WazoConfdError


class EndpointsService:

    def __init__(self, confd_client, ari):
        self._confd = confd_client
        self._ari = ari

    def list_trunks(self, tenant_uuid):
        try:
            result = self._confd.trunks.list(tenant_uuid=tenant_uuid)
        except HTTPError as e:
            raise WazoConfdError(self._confd, e)

        total = filtered = result['total']

        results = []
        endpoints = [endpoint.json for endpoint in self._ari.endpoints.list()]
        for confd_trunk in result['items']:
            trunk = self._build_static_fields(confd_trunk)
            trunk = self._build_dynamic_fields(trunk, endpoints)
            results.append(trunk)

        return results, total, filtered

    def _build_dynamic_fields(self, trunk, endpoints):
        if trunk.get('technology') != 'sip':
            return trunk

        name = trunk['name']
        for endpoint in endpoints:
            if endpoint['resource'] != name:
                continue
            trunk['registered'] = endpoint['state'] == 'online'
            trunk['current_call_count'] = len(endpoint['channel_ids'])

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
