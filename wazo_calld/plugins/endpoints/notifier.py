# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_bus.resources.line.event import LineStatusUpdatedEvent
from wazo_bus.resources.trunk.event import TrunkStatusUpdatedEvent

from .identity import TRUNK


class EndpointStatusNotifier:
    _asterisk_to_confd_techno_map = {
        'PJSIP': 'sip',
        'IAX2': 'iax',
        'SCCP': 'sccp',
    }

    def __init__(self, publisher, identities):
        self._publisher = publisher
        self._identities = identities

    def endpoint_updated(self, endpoint):
        identity = self._identities.identity_of(endpoint.techno, endpoint.name)
        if not identity:
            return

        techno = self._asterisk_to_confd_techno_map[endpoint.techno]
        event_class = (
            TrunkStatusUpdatedEvent
            if identity.kind == TRUNK
            else LineStatusUpdatedEvent
        )
        event = event_class(
            identity.id,
            techno,
            endpoint.name,
            endpoint.registered,
            endpoint.current_call_count,
            identity.tenant_uuid,
        )
        return self._publisher.publish(event)
