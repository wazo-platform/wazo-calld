# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from wazo_bus.resources.line.event import LineStatusUpdatedEvent
from wazo_bus.resources.trunk.event import TrunkStatusUpdatedEvent

logger = logging.getLogger(__name__)


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
        techno = self._asterisk_to_confd_techno_map.get(
            endpoint.techno, endpoint.techno
        )

        trunk = self._confd_cache.get_trunk(endpoint.techno, endpoint.name)
        if trunk:
            event = TrunkStatusUpdatedEvent(
                trunk['id'],
                techno,
                endpoint.name,
                endpoint.registered,
                endpoint.current_call_count,
                trunk['tenant_uuid'],
            )
            return self._publisher.publish(event)

        line = self._confd_cache.get_line(endpoint.techno, endpoint.name)
        if line:
            event = LineStatusUpdatedEvent(
                line['id'],
                techno,
                endpoint.name,
                endpoint.registered,
                endpoint.current_call_count,
                line['tenant_uuid'],
            )
            return self._publisher.publish(event)

        if not self._confd_cache.ready:
            logger.debug(
                'dropping status of %s/%s: endpoint cache not loaded yet',
                endpoint.techno,
                endpoint.name,
            )
