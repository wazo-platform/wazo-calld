# Copyright 2021-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock, patch

from ..stasis import SwitchboardsStasis


class TestStasis(TestCase):
    def test_unhandled_error_during_stasis(self):
        ari, confd, notifier, service = Mock(), Mock(), Mock(), Mock()
        stasis = SwitchboardsStasis(ari, confd, notifier, service)
        channel = Mock()

        event = {
            'args': ['switchboard', 'switchboard_queue']
        }  # The second argument is missing
        event_objects = {'channel': channel}

        with patch.object(stasis, '_stasis_start_queue', Mock(side_effect=Exception)):
            stasis.stasis_start(event_objects, event)

        ari.client.channels.continueInDialplan.assert_called_once_with(
            channelId=channel.id
        )

    def test_unqueue_ignores_channel_with_empty_switchboard_uuid(self):
        ari, confd, notifier, service = Mock(), Mock(), Mock(), Mock()
        stasis = SwitchboardsStasis(ari, confd, notifier, service)
        channel = Mock()
        channel.json = {'channelvars': {'WAZO_SWITCHBOARD_QUEUE': ''}}

        stasis.unqueue(channel, event={})

        service.queued_calls.assert_not_called()
        notifier.queued_calls.assert_not_called()

    def test_unqueue_notifies_queued_calls(self):
        ari, confd, notifier, service = Mock(), Mock(), Mock(), Mock()
        stasis = SwitchboardsStasis(ari, confd, notifier, service)
        channel = Mock()
        channel.json = {
            'channelvars': {
                'WAZO_SWITCHBOARD_QUEUE': 'switchboard-uuid',
                'WAZO_TENANT_UUID': 'tenant-uuid',
            }
        }

        stasis.unqueue(channel, event={})

        service.queued_calls.assert_called_once_with('tenant-uuid', 'switchboard-uuid')
        notifier.queued_calls.assert_called_once_with(
            'tenant-uuid', 'switchboard-uuid', service.queued_calls.return_value
        )

    def test_unhold_ignores_channel_with_empty_switchboard_uuid(self):
        ari, confd, notifier, service = Mock(), Mock(), Mock(), Mock()
        stasis = SwitchboardsStasis(ari, confd, notifier, service)
        channel = Mock()
        channel.json = {'channelvars': {'WAZO_SWITCHBOARD_HOLD': ''}}

        stasis.unhold(channel, event={})

        service.held_calls.assert_not_called()
        notifier.held_calls.assert_not_called()

    def test_unhold_notifies_held_calls(self):
        ari, confd, notifier, service = Mock(), Mock(), Mock(), Mock()
        stasis = SwitchboardsStasis(ari, confd, notifier, service)
        channel = Mock()
        channel.json = {
            'channelvars': {
                'WAZO_SWITCHBOARD_HOLD': 'switchboard-uuid',
                'WAZO_TENANT_UUID': 'tenant-uuid',
            }
        }

        stasis.unhold(channel, event={})

        service.held_calls.assert_called_once_with('tenant-uuid', 'switchboard-uuid')
        notifier.held_calls.assert_called_once_with(
            'tenant-uuid', 'switchboard-uuid', service.held_calls.return_value
        )
