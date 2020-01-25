# Copyright 2016-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests

from hamcrest import (
    assert_that,
    calling,
    contains_string,
    has_properties
)
from xivo_test_helpers import until
from xivo_test_helpers.hamcrest.raises import raises
from wazo_calld_client.exceptions import CalldError

from .helpers.base import IntegrationTest
from .helpers.wait_strategy import CalldUpWaitStrategy


class TestNoARI(IntegrationTest):

    asset = 'no_ari'
    wait_strategy = CalldUpWaitStrategy()

    def test_given_no_ari_then_return_503(self):
        assert_that(
            calling(self.calld_client.calls.list_calls),
            raises(CalldError).matching(has_properties(
                status_code=503,
                error_id='asterisk-ari-not-initialized',
            ))
        )


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
