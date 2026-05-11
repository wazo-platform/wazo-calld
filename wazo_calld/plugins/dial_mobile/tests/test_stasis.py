# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock
from unittest.mock import sentinel as s

from hamcrest import assert_that, calling, not_
from wazo_test_helpers.hamcrest.raises import raises

from ..stasis import DialMobileStasis


class TestStasisStart(TestCase):
    def setUp(self):
        self.core_ari = Mock()
        self.ari = Mock()
        self.core_ari.client = self.ari
        self.service = Mock()

        self.stasis = DialMobileStasis(self.core_ari, self.service)

    def test_other_application(self):
        assert_that(
            calling(self.stasis.stasis_start).with_args(
                Mock(), {'application': 'foobar'}
            ),
            not_(raises(Exception)),
        )

        self.service.dial_all_contacts.assert_not_called()
        self.service.join_bridge.assert_not_called()

    def test_not_enough_arguments_does_nothing(self):
        wrong_arguments = [
            [],
            ['dial'],
            ['join'],
            ['pickup', 'exten'],
        ]
        for args in wrong_arguments:
            event = {
                'application': DialMobileStasis._app_name,
                'args': args,
                'channel': {'id': s.channel_id, 'name': s.channel_name},
            }
            assert_that(
                calling(self.stasis.stasis_start).with_args(
                    Mock(),
                    event,
                ),
                not_(raises(Exception)),
                args,
            )

            self.service.dial_all_contacts.assert_not_called()
            self.service.join_bridge.assert_not_called()
            self.service.find_bridge_by_exten_context.assert_not_called()

    def test_calling_dial(self):
        self.stasis.stasis_start(
            Mock(),
            {
                'application': DialMobileStasis._app_name,
                'args': ['dial', s.aor],
                'channel': {
                    'id': s.channel_id,
                    'name': s.channel_name,
                    'channelvars': {'CHANNEL(linkedid)': s.linkedid},
                },
            },
        )

        self.service.dial_all_contacts.assert_called_once_with(
            s.channel_id, s.linkedid, s.aor
        )
        self.service.join_bridge.assert_not_called()

    def test_calling_join(self):
        self.stasis.stasis_start(
            Mock(),
            {
                'application': DialMobileStasis._app_name,
                'args': ['join', s.bridge_uuid],
                'channel': {
                    'id': s.channel_id,
                    'name': s.channel_name,
                    'channelvars': {'CHANNEL(linkedid)': s.linkedid},
                },
            },
        )

        self.service.dial_all_contacts.assert_not_called()
        self.service.join_bridge.called_once_with(s.channel_id, s.bridge_uuid)

    def test_calling_pickup(self):
        self.stasis.stasis_start(
            Mock(),
            {
                'application': DialMobileStasis._app_name,
                'args': ['pickup', s.exten, s.context],
                'channel': {
                    'id': s.channel_id,
                    'name': s.channel_name,
                    'channelvars': {'CHANNEL(linkedid)': s.linkedid},
                },
            },
        )

        self.service.dial_all_contacts.assert_not_called()
        self.service.find_bridge_by_exten_context.assert_called_once_with(
            s.exten, s.context
        )
        self.service.join_bridge.called_once_with(
            s.channel_id, self.service.find_bridge_by_exten_context.return_value
        )

    def test_calling_pickup_not_found(self):
        self.service.find_bridge_by_exten_context.return_value = None

        self.stasis.stasis_start(
            Mock(),
            {
                'application': DialMobileStasis._app_name,
                'args': ['pickup', s.exten, s.context],
                'channel': {
                    'id': s.channel_id,
                    'name': s.channel_name,
                    'channelvars': {'CHANNEL(linkedid)': s.linkedid},
                },
            },
        )

        self.service.dial_all_contacts.assert_not_called()
        self.service.find_bridge_by_exten_context.assert_called_once_with(
            s.exten, s.context
        )
        self.service.join_bridge.assert_not_called()

        self.core_ari.client.channels.continueInDialplan.assert_called_once_with(
            channelId=s.channel_id
        )

    def channel_left(self):
        self.stasis.on_channel_left_bridge(
            Mock(),
            {
                'application': DialMobileStasis._app_name,
                'bridge': {'id': s.bridge_uuid},
            },
        )

        self.service.clean_bridge.assert_called_once_with(s.bridge_uuid)


class TestEndpointSubscription(TestCase):
    def setUp(self):
        self.core_ari = Mock()
        self.ari = Mock()
        self.core_ari.client = self.ari
        self.service = Mock()
        self.stasis = DialMobileStasis(self.core_ari, self.service)

    def test_subscribe_wires_endpoint_subscription_on_app_registered(self):
        self.stasis._subscribe()

        self.ari.on_application_registered.assert_any_call(
            DialMobileStasis._app_name,
            self.stasis.subscribe_to_pjsip_endpoint_events,
        )
        self.ari.on_application_deregistered.assert_any_call(
            DialMobileStasis._app_name,
            self.stasis.unsubscribe_from_pjsip_endpoint_events,
        )

    def test_subscribe_to_pjsip_endpoint_events(self):
        self.stasis.subscribe_to_pjsip_endpoint_events()

        self.ari.applications.subscribe.assert_called_once_with(
            applicationName=DialMobileStasis._app_name,
            eventSource='endpoint:PJSIP',
        )

    def test_unsubscribe_from_pjsip_endpoint_events(self):
        self.stasis.unsubscribe_from_pjsip_endpoint_events()

        self.ari.applications.unsubscribe.assert_called_once_with(
            applicationName=DialMobileStasis._app_name,
            eventSource='endpoint:PJSIP',
        )


class TestContactStatusChange(TestCase):
    def setUp(self):
        self.core_ari = Mock()
        self.ari = Mock()
        self.core_ari.client = self.ari
        self.service = Mock()
        self.stasis = DialMobileStasis(self.core_ari, self.service)

    def _event(self, contact_status='Reachable', aor='9vCJK5Ob'):
        return {
            'type': 'ContactStatusChange',
            'application': DialMobileStasis._app_name,
            'endpoint': {
                'technology': 'PJSIP',
                'resource': aor,
                'state': 'online',
                'channel_ids': [],
            },
            'contact_info': {
                'uri': f'sip:{aor}@127.0.0.1:54332;transport=WS',
                'contact_status': contact_status,
                'aor': aor,
                'roundtrip_usec': '0',
            },
        }

    def test_dialable_statuses_route_to_service(self):
        for status in ('Created', 'NonQualified', 'Reachable'):
            self.service.notify_contact_available.reset_mock()
            self.stasis.on_contact_status_change(Mock(), self._event(status))
            self.service.notify_contact_available.assert_called_once_with('9vCJK5Ob')

    def test_unreachable_statuses_ignored(self):
        for status in ('Unreachable', 'Removed', 'Unknown'):
            self.service.notify_contact_available.reset_mock()
            self.stasis.on_contact_status_change(Mock(), self._event(status))
            self.service.notify_contact_available.assert_not_called()

    def test_other_application_ignored(self):
        event = self._event('Reachable')
        event['application'] = 'somethingelse'

        self.stasis.on_contact_status_change(Mock(), event)

        self.service.notify_contact_available.assert_not_called()
