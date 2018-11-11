# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests

from hamcrest import assert_that
from hamcrest import contains_string
from xivo_test_helpers import until

from .helpers.base import IntegrationTest
from .helpers.wait_strategy import NoWaitStrategy


class TestNoARI(IntegrationTest):

    asset = 'no_ari'
    wait_strategy = NoWaitStrategy()

    def test_given_no_ari_when_ctid_ng_starts_then_ctid_ng_stops(self):
        def ctid_ng_is_stopped():
            status = self.service_status()
            return not status['State']['Running']

        until.true(ctid_ng_is_stopped, tries=10, message='xivo-ctid-ng did not stop while starting with no ARI')

        log = self.service_logs()
        assert_that(log, contains_string("ARI server unreachable... stopping"))


class TestARIReconnection(IntegrationTest):

    asset = 'quick_ari_reconnect'

    def test_when_asterisk_restart_then_ctid_ng_reconnects(self):
        until.true(self._ctid_ng_is_connected, tries=3)

        self.restart_service('ari')
        self.reset_clients()

        assert_that(self.service_logs(), contains_string("ARI connection error"))

        until.true(self._ctid_ng_is_connected, tries=3)

    def _ctid_ng_is_connected(self):
        try:
            ws = self.ari.websockets()
        except requests.ConnectionError:
            ws = []

        return len(ws) > 0

    def _ctid_ng_is_not_connected(self):
        return not self._ctid_ng_is_connected()

    def test_when_asterisk_sends_non_json_events_then_ctid_ng_reconnects(self):
        self.stasis.non_json_message()

        until.false(self._ctid_ng_is_not_connected, tries=3, message='xivo-ctid-ng did not disconnect from ARI')
        until.true(self._ctid_ng_is_connected, tries=3, message='xivo-ctid-ng did not reconnect to ARI')

    '''Other tests I don't know how to implement:

    - When ARI is cut off (power stopped or firewall drops everything), then
      xivo-ctid-ng should also try to reconnect.
    - When ARI is cut off, and xivo-ctid-ng is waiting for it to time out, if
      xivo-ctid-ng is stopped at this moment, it should stop trying to reconnect
      and exit
    '''
