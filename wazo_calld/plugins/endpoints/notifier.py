# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_bus.resources.line.event import LineStatusUpdatedEvent
from wazo_bus.resources.trunk.event import TrunkStatusUpdatedEvent

_HOLD = object()


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
        # `endpoint` is a snapshot (NotifyingStatusCache), safe to hold as is
        with self._confd_cache.lock:
            target = self._resolve(endpoint)
            if target is _HOLD:
                key = (endpoint.techno, endpoint.name)
                self._confd_cache.held_endpoints[key] = endpoint
                return
        if target:
            self._publish(endpoint, *target)

    def replay(self, kind):
        """Publish the held notifications the index just made resolvable.

        Once lines are ready (trunks load first) nothing is held any more: an
        endpoint neither index knows is dropped, as it always was.
        """
        resolved = []
        with self._confd_cache.lock:
            held = self._confd_cache.held_endpoints
            for key, endpoint in list(held.items()):
                target = self._resolve(endpoint)
                if target is _HOLD:
                    continue
                del held[key]
                if target:
                    resolved.append((endpoint, target))
        for endpoint, target in resolved:
            self._publish(endpoint, *target)

    def _resolve(self, endpoint):
        cache = self._confd_cache
        if not cache.trunks_ready:
            return _HOLD
        if trunk := cache.get_trunk(endpoint.techno, endpoint.name):
            return TrunkStatusUpdatedEvent, trunk
        if not cache.lines_ready:
            return _HOLD
        if line := cache.get_line(endpoint.techno, endpoint.name):
            return LineStatusUpdatedEvent, line
        return None

    def _publish(self, endpoint, event_class, confd_endpoint):
        techno = self._asterisk_to_confd_techno_map.get(
            endpoint.techno, endpoint.techno
        )
        event = event_class(
            confd_endpoint['id'],
            techno,
            endpoint.name,
            endpoint.registered,
            endpoint.current_call_count,
            confd_endpoint['tenant_uuid'],
        )
        self._publisher.publish(event)
