# Copyright 2019-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase

from unittest.mock import (
    Mock,
    sentinel as s,
)
from hamcrest import (
    assert_that,
    calling,
    not_,
)
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
        arguments = [
            ['dial'],
            ['join'],
            ['pickup', 'exten'],
        ]
        for args in arguments:
            event = {
                'application': DialMobileStasis._app_name,
                'args': args,
                'channel': {'id': s.channel_id},
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
                    'channelvars': {'CHANNEL(linkedid)': s.linkedid},
                },
            },
        )

        self.service.dial_all_contacts.assert_not_called()
        self.service.find_bridge_by_exten_context.assert_called_once_with(s.exten, s.context)
        self.service.join_bridge.called_once_with(s.channel_id, self.service.find_bridge_by_exten_context.return_value)

    def test_calling_pickup_not_found(self):
        self.service.find_bridge_by_exten_context.return_value = None

        self.stasis.stasis_start(
            Mock(),
            {
                'application': DialMobileStasis._app_name,
                'args': ['pickup', s.exten, s.context],
                'channel': {
                    'id': s.channel_id,
                    'channelvars': {'CHANNEL(linkedid)': s.linkedid},
                },
            },
        )

        self.service.dial_all_contacts.assert_not_called()
        self.service.find_bridge_by_exten_context.assert_called_once_with(s.exten, s.context)
        self.service.join_bridge.assert_not_called()

        self.core_ari.client.channels.continueInDialplan.assert_called_once_with(channelId=s.channel_id)

    def channel_left(self):
        self.stasis.on_channel_left_bridge(
            Mock(),
            {
                'application': DialMobileStasis._app_name,
                'bridge': {'id': s.bridge_uuid},
            },
        )

        self.service.clean_bridge.assert_called_once_with(s.bridge_uuid)
