# Copyright 2016-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that, calling, has_entries, has_items, has_properties
from wazo_test_helpers import until
from wazo_test_helpers.hamcrest.raises import raises
from wazo_calld_client.exceptions import CalldError

from .helpers.base import IntegrationTest
from .helpers.wait_strategy import CalldUpWaitStrategy, CalldEverythingOkWaitStrategy
from .helpers.real_asterisk import RealAsteriskIntegrationTest


class TestNoARI(IntegrationTest):
    asset = 'no_ari'
    wait_strategy = CalldUpWaitStrategy()

    def test_given_no_ari_then_return_503(self):
        assert_that(
            calling(self.calld_client.calls.list_calls),
            raises(CalldError).matching(
                has_properties(
                    status_code=503,
                    error_id='asterisk-ari-not-initialized',
                )
            ),
        )


class TestARIReconnection(RealAsteriskIntegrationTest):
    asset = 'real_asterisk'
    wait_strategy = CalldEverythingOkWaitStrategy()

    def test_when_asterisk_restart_then_calld_reconnects(self):
        until.assert_(self._calld_is_connected, tries=3)

        self.restart_service('ari')
        self.reset_clients()

        def reconnect():
            try:
                self.reconnect_ari()
                return True
            except Exception:
                return False

        until.true(reconnect, tries=3)

        until.assert_(self._calld_is_connected, tries=10)

    def _calld_is_connected(self):
        assert_that(
            self.calld.status(),
            has_entries(
                ari=has_entries(status='ok'),
                bus_consumer=has_entries(status='ok'),
            ),
        )
        registered_applications = [
            application['name'] for application in self.ari.applications.list()
        ]
        assert_that(
            registered_applications,
            has_items(
                'adhoc_conference',
                'callcontrol',
                'dial_mobile',
            ),
        )

    def _consumer_reconnected(self):
        return (
            "Exception occurred in thread 'consumer', restarting..."
            in self.service_logs()
        )

    def test_when_asterisk_sends_non_json_events_then_calld_reconnects(self):
        self.bus.send_stasis_non_json_event()

        until.true(
            self._consumer_reconnected,
            tries=5,
            message='wazo-calld did non raise an exception',
        )
        until.assert_(
            self._calld_is_connected,
            tries=3,
            message='wazo-calld did not reconnect to ARI',
        )

    '''Other tests I don't know how to implement:

    - When ARI is cut off (power stopped or firewall drops everything), then
      wazo-calld should also try to reconnect.
    - When ARI is cut off, and wazo-calld is waiting for it to time out, if
      wazo-calld is stopped at this moment, it should stop trying to reconnect
      and exit
    '''
