# Copyright 2019-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase

from mock import (
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

        self.stasis = DialMobileStasis(self.ari, self.service)

    def test_other_application(self):
        assert_that(
            calling(self.stasis.stasis_start).with_args(Mock(), {'application': 'foobar'}),
            not_(raises(Exception)),
        )

        self.service.dial_all_contacts.assert_not_called()
        self.service.join_bridge.assert_not_called()

    def test_not_enough_arguments_does_nothing(self):
        assert_that(
            calling(self.stasis.stasis_start).with_args(Mock(), {
                'application': DialMobileStasis._app_name,
                'args': ['dial'],
            }),
            not_(raises(Exception)),
        )

        self.service.dial_all_contacts.assert_not_called()
        self.service.join_bridge.assert_not_called()

    def test_calling_dial(self):
        self.stasis.stasis_start(
            Mock(),
            {
                'application': DialMobileStasis._app_name,
                'args': ['dial', s.aor],
                'channel': {'id': s.channel_id},
            },
        )

        self.service.dial_all_contacts.assert_called_once_with(s.channel_id, s.aor)
        self.service.join_bridge.assert_not_called()

    def test_calling_join(self):
        self.stasis.stasis_start(
            Mock(),
            {
                'application': DialMobileStasis._app_name,
                'args': ['join', s.bridge_uuid],
                'channel': {'id': s.channel_id},
            },
        )

        self.service.dial_all_contacts.assert_not_called()
        self.service.join_bridge.called_once_with(s.channel_id, s.bridge_uuid)

    def channel_left(self):
        self.stasis.on_channel_left_bridge(
            Mock(),
            {
                'application': DialMobileStasis._app_name,
                'bridge': {'id': s.bridge_uuid},
            },
        )

        self.service.clean_bridge.assert_called_once_with(s.bridge_uuid)
