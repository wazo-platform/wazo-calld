# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock, sentinel as s

from ..notifier import (
    EndpointStatusNotifier,
    LineStatusUpdatedEvent,
    TrunkStatusUpdatedEvent,
)
from ..services import Endpoint


class TestEndpointStatusNotifier(TestCase):

    def setUp(self):
        self.confd_cache = Mock()
        self.publisher = Mock()

        self.notifier = EndpointStatusNotifier(self.publisher, self.confd_cache)

    def test_trunk_updated(self):
        trunk = {'id': s.trunk_id, 'tenant_uuid': s.tenant_uuid}
        self.confd_cache.get_trunk.return_value = trunk
        self.confd_cache.get_line.return_value = None
        endpoint = Endpoint(
            techno='PJSIP',
            name=s.name,
            registered=True,
            channel_ids=[1, 2, 3],
        )

        self.notifier.endpoint_updated(endpoint)

        self.publisher.publish.assert_called_once_with(
            TrunkStatusUpdatedEvent({
                'id': s.trunk_id,
                'technology': 'sip',
                'name': s.name,
                'registered': True,
                'current_call_count': 3,
            }),
            headers={'tenant_uuid': s.tenant_uuid},
        )

    def test_line_updated(self):
        line = {'id': s.line_id, 'tenant_uuid': s.tenant_uuid}
        self.confd_cache.get_line.return_value = line
        self.confd_cache.get_trunk.return_value = None
        endpoint = Endpoint(
            techno='SCCP',
            name=s.name,
            registered=True,
            channel_ids=[1, 2, 3],
        )

        self.notifier.endpoint_updated(endpoint)

        self.publisher.publish.assert_called_once_with(
            LineStatusUpdatedEvent({
                'id': s.line_id,
                'technology': 'sccp',
                'name': s.name,
                'registered': True,
                'current_call_count': 3,
            }),
            headers={'tenant_uuid': s.tenant_uuid},
        )
