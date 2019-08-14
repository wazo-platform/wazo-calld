# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase

from mock import Mock
from hamcrest import (
    assert_that,
    calling,
    not_,
)
from xivo_test_helpers.hamcrest.raises import raises

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
