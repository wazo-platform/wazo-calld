# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_bus.resources.common.event import ArbitraryEvent


class EndpointStatusNotifier:
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
            'technology': endpoint.techno,
            'name': endpoint.name,
            'registered': endpoint.registered,
            'current_call_count': endpoint.current_call_count,
        }

        routing_key = 'endpoints.{}.status.updated'.format(trunk['id'])
        event = ArbitraryEvent(
            name='trunk_status_updated',
            body=body,
            required_acl='events.{}'.format(routing_key),
        )
        event.routing_key = routing_key
        headers = {'tenant_uuid': trunk['tenant_uuid']}
        self._publisher.publish(event, headers=headers)
