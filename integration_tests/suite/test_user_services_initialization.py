# Copyright 2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import uuid

from hamcrest import (
    assert_that,
    empty,
    has_entries,
    has_item,
)
from xivo_test_helpers import until

from .helpers.base import IntegrationTest
from .helpers.confd import MockUser
from .helpers.wait_strategy import CalldEverythingOkWaitStrategy


class TestUserServicesInitialization(IntegrationTest):

    asset = 'basic_rest'
    wait_strategy = CalldEverythingOkWaitStrategy()

    def setUp(self):
        super().setUp()
        self.amid.reset()
        self.ari.reset()
        self.confd.reset()

    def test_dnd_enabled_when_calld_is_down(self):
        user = MockUser(
            str(uuid.uuid4()),
            services={'dnd': {'enabled': True}},
            groups=['group1'],
        )
        with self._calld_stopped():
            self.confd.set_users(user)

        def assert_amid_request():
            assert_that(
                self.amid.requests()['requests'],
                has_item(
                    has_entries(
                        {
                            'method': 'POST',
                            'path': '/1.0/action/QueuePause',
                            'json': has_entries(
                                {
                                    'Interface': f'Local/{user.uuid()}@usersharedlines',
                                    'Paused': True,
                                }
                            ),
                        }
                    ),
                ),
            )

        until.assert_(assert_amid_request, tries=5)

    def test_dnd_disabled_when_calld_is_down(self):
        user = MockUser(
            str(uuid.uuid4()),
            services={'dnd': {'enabled': False}},
            groups=['group1'],
        )
        with self._calld_stopped():
            self.confd.set_users(user)

        def assert_amid_request():
            assert_that(
                self.amid.requests()['requests'],
                has_item(
                    has_entries(
                        {
                            'method': 'POST',
                            'path': '/1.0/action/QueuePause',
                            'json': has_entries(
                                {
                                    'Interface': f'Local/{user.uuid()}@usersharedlines',
                                    'Paused': False,
                                }
                            ),
                        }
                    ),
                ),
            )

        until.assert_(assert_amid_request, tries=5)

    def test_dnd_enabled_when_calld_is_down_and_users_has_no_groups(self):
        user = MockUser(
            str(uuid.uuid4()),
            services={'dnd': {'enabled': True}},
        )
        with self._calld_stopped():
            self.confd.set_users(user)

        assert_that(self.amid.requests()['requests'], empty())

    def test_dnd_disabled_when_calld_is_down_and_users_has_no_services(self):
        user = MockUser(
            str(uuid.uuid4()),
            groups=['group1'],
        )
        with self._calld_stopped():
            self.confd.set_users(user)

        def assert_amid_request():
            assert_that(
                self.amid.requests()['requests'],
                has_item(
                    has_entries(
                        {
                            'method': 'POST',
                            'path': '/1.0/action/QueuePause',
                            'json': has_entries(
                                {
                                    'Interface': f'Local/{user.uuid()}@usersharedlines',
                                    'Paused': False,
                                }
                            ),
                        }
                    ),
                ),
            )

        until.assert_(assert_amid_request, tries=5)
