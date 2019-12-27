# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_bus.resources.trunk.event import TrunkStatusUpdatedEvent
from xivo_bus.resources.line.event import LineStatusUpdatedEvent


class EndpointStatusNotifier:
    _asterisk_to_confd_techno_map = {
        'PJSIP': 'sip',
        'IAX2': 'iax',
        'SCCP': 'sccp',
    }

    def __init__(self, publisher, confd_cache):
        self._publisher = publisher
        self._confd_cache = confd_cache

    def endpoint_updated(self, endpoint):
        techno = self._asterisk_to_confd_techno_map.get(endpoint.techno, endpoint.techno)
        body = {
            'technology': techno,
            'name': endpoint.name,
            'registered': endpoint.registered,
            'current_call_count': endpoint.current_call_count,
        }

        trunk = self._confd_cache.get_trunk(endpoint.techno, endpoint.name)
        if trunk:
            body['id'] = trunk['id']
            event = TrunkStatusUpdatedEvent(body)
            headers = {'tenant_uuid': trunk['tenant_uuid']}

        line = self._confd_cache.get_line(endpoint.techno, endpoint.name)
        if line:
            body['id'] = line['id']
            event = LineStatusUpdatedEvent(body)
            headers = {'tenant_uuid': line['tenant_uuid']}

        self._publisher.publish(event, headers=headers)
