# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_bus.resources.trunk.event import TrunkStatusUpdatedEvent


class EndpointStatusNotifier:
    _asterisk_to_confd_techno_map = {
        'PJSIP': 'sip',
        'IAX2': 'iax',
    }

    def __init__(self, publisher, confd_cache):
        self._publisher = publisher
        self._confd_cache = confd_cache

    def endpoint_updated(self, endpoint):
        trunk = self._confd_cache.get_trunk(endpoint.techno, endpoint.name)
        if not trunk:
            # This is a line, ignore it at the moment
            return

        body = {
            'id': trunk['id'],
            'type': 'trunk',
            'technology': self._asterisk_to_confd_techno_map.get(endpoint.techno, endpoint.techno),
            'name': endpoint.name,
            'registered': endpoint.registered,
            'current_call_count': endpoint.current_call_count,
        }

        event = TrunkStatusUpdatedEvent(body)
        headers = {'tenant_uuid': trunk['tenant_uuid']}
        self._publisher.publish(event, headers=headers)
