# Copyright 2016-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import (
    assert_that,
    equal_to,
    has_entries,
    has_entry,
)
from wazo_test_helpers import until

from .helpers.base import IntegrationTest
from .helpers.wait_strategy import (
    CalldConnectionsOkWaitStrategy,
    CalldEverythingOkWaitStrategy,
    CalldUpWaitStrategy,
)


class TestStatusNoARI(IntegrationTest):

    asset = 'no_ari'
    wait_strategy = CalldUpWaitStrategy()

    def test_given_no_ari_when_status_then_ari_fail(self):
        result = self.calld.status()

        assert_that(result['ari']['status'], equal_to('fail'))


class TestStatusARIStops(IntegrationTest):

    asset = 'basic_rest'
    wait_strategy = CalldConnectionsOkWaitStrategy()

    def test_given_ari_stops_when_status_then_ari_fail(self):
        self.stop_service('ari')

        def ari_is_down():
            result = self.calld.status()
            assert_that(result['ari']['status'], equal_to('fail'))

        until.assert_(ari_is_down, tries=5)


class TestStatusNoRabbitMQ(IntegrationTest):

    asset = 'no_rabbitmq'
    wait_strategy = CalldUpWaitStrategy()

    def test_given_no_rabbitmq_when_status_then_rabbitmq_fail(self):
        result = self.calld.status()

        assert_that(result['bus_consumer']['status'], equal_to('fail'))


class TestStatusRabbitMQStops(IntegrationTest):

    asset = 'basic_rest'
    wait_strategy = CalldConnectionsOkWaitStrategy()

    def test_given_rabbitmq_stops_when_status_then_rabbitmq_fail(self):
        self.stop_service('rabbitmq')

        def rabbitmq_is_down():
            result = self.calld.status()
            assert_that(result['bus_consumer']['status'], equal_to('fail'))

        until.assert_(rabbitmq_is_down, tries=5)


class TestStatusAllOK(IntegrationTest):

    asset = 'real_asterisk'
    wait_strategy = CalldEverythingOkWaitStrategy()

    def test_given_auth_and_ari_and_rabbitmq_when_status_then_status_ok(self):

        def all_ok():
            result = self.calld.status()
            assert_that(result, has_entries(
                ari=has_entry('status', 'ok'),
                bus_consumer=has_entry('status', 'ok'),
                service_token=has_entry('status', 'ok'),
            ))

        until.assert_(all_ok, tries=10)
