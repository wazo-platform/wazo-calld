# Copyright 2016-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests

from hamcrest import assert_that
from hamcrest import contains_string
from xivo_test_helpers import until

from .helpers.base import IntegrationTest
from .helpers.wait_strategy import NoWaitStrategy


class TestNoARI(IntegrationTest):

    asset = 'no_ari'
    wait_strategy = NoWaitStrategy()

    def test_given_no_ari_when_calld_starts_then_calld_stops(self):
        def calld_is_stopped():
            status = self.service_status()
            return not status['State']['Running']

        until.true(calld_is_stopped, tries=10, message='wazo-calld did not stop while starting with no ARI')

        log = self.service_logs()
        assert_that(log, contains_string("ARI server unreachable... stopping"))


class TestARIReconnection(IntegrationTest):

    asset = 'quick_ari_reconnect'

    def test_when_asterisk_restart_then_calld_reconnects(self):
        until.true(self._calld_is_connected, tries=3)

        self.restart_service('ari')
        self.reset_clients()

        assert_that(self.service_logs(), contains_string("ARI connection error"))

        until.true(self._calld_is_connected, tries=3)

    def _calld_is_connected(self):
        try:
            ws = self.ari.websockets()
        except requests.ConnectionError:
            ws = []

        return len(ws) > 0

    def _calld_is_not_connected(self):
        return not self._calld_is_connected()

    def test_when_asterisk_sends_non_json_events_then_calld_reconnects(self):
        self.stasis.non_json_message()

        until.false(self._calld_is_not_connected, tries=3, message='wazo-calld did not disconnect from ARI')
        until.true(self._calld_is_connected, tries=3, message='wazo-calld did not reconnect to ARI')

    '''Other tests I don't know how to implement:

    - When ARI is cut off (power stopped or firewall drops everything), then
      wazo-calld should also try to reconnect.
    - When ARI is cut off, and wazo-calld is waiting for it to time out, if
      wazo-calld is stopped at this moment, it should stop trying to reconnect
      and exit
    '''
