# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import sentinel as s

from ..identity import EndpointIdentity
from ..notifier import (
    EndpointStatusNotifier,
    LineStatusUpdatedEvent,
    TrunkStatusUpdatedEvent,
)
from ..services import Endpoint


class TestEndpointStatusNotifier(TestCase):
    def setUp(self):
        self.identities = Mock()
        self.publisher = Mock()

        self.notifier = EndpointStatusNotifier(self.publisher, self.identities)

    def test_trunk_updated(self):
        self.identities.identity_of.return_value = EndpointIdentity(
            'trunk', s.trunk_id, s.tenant_uuid
        )
        endpoint = Endpoint(
            techno='PJSIP',
            name=s.name,
            registered=True,
            channel_ids=[1, 2, 3],
        )

        self.notifier.endpoint_updated(endpoint)

        self.identities.identity_of.assert_called_once_with('PJSIP', s.name)
        self.publisher.publish.assert_called_once_with(
            TrunkStatusUpdatedEvent(s.trunk_id, 'sip', s.name, True, 3, s.tenant_uuid)
        )

    def test_line_updated(self):
        self.identities.identity_of.return_value = EndpointIdentity(
            'line', s.line_id, s.tenant_uuid
        )
        endpoint = Endpoint(
            techno='SCCP',
            name=s.name,
            registered=True,
            channel_ids=[1, 2, 3],
        )

        self.notifier.endpoint_updated(endpoint)

        self.publisher.publish.assert_called_once_with(
            LineStatusUpdatedEvent(s.line_id, 'sccp', s.name, True, 3, s.tenant_uuid)
        )

    def test_iax_trunk_updated(self):
        self.identities.identity_of.return_value = EndpointIdentity(
            'trunk', s.trunk_id, s.tenant_uuid
        )
        endpoint = Endpoint('IAX2', s.name, registered=None, channel_ids=[])

        self.notifier.endpoint_updated(endpoint)

        self.publisher.publish.assert_called_once_with(
            TrunkStatusUpdatedEvent(s.trunk_id, 'iax', s.name, None, 0, s.tenant_uuid)
        )

    def test_nothing_published_without_identity(self):
        self.identities.identity_of.return_value = None
        endpoint = Endpoint('PJSIP', s.name, registered=True, channel_ids=[])

        self.notifier.endpoint_updated(endpoint)

        self.publisher.publish.assert_not_called()
