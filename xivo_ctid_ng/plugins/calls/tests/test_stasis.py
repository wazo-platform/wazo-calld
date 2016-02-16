# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import calling
from hamcrest import equal_to
from hamcrest import is_
from hamcrest import raises
from mock import Mock
from mock import sentinel as s
from requests.exceptions import HTTPError
from unittest import TestCase

from ..stasis import ConnectCallEvent
from ..stasis import InvalidConnectCallEvent
from ..stasis import InvalidStartCallEvent
from ..stasis import StartCallEvent


class TestStartCallEvent(TestCase):

    def test_get_stasis_start_app_invalid(self):
        assert_that(calling(StartCallEvent).with_args(channel=Mock(),
                                                      event={},
                                                      state_persistor=Mock()),
                    raises(InvalidStartCallEvent))
        assert_that(calling(StartCallEvent).with_args(channel=Mock(),
                                                      event={'args': []},
                                                      state_persistor=Mock()),
                    raises(InvalidStartCallEvent))

    def test_get_stasis_start_app_valid(self):
        event = {
            'application': 'myapp',
            'args': ['red']
        }

        result = StartCallEvent(channel=Mock(),
                                event=event,
                                state_persistor=Mock())

        assert_that(result.app, equal_to('myapp'))
        assert_that(result.app_instance, equal_to('red'))


class TestConnectCallEvent(TestCase):

    def test_is_connect_event_false(self):
        assert_that(ConnectCallEvent.is_connect_event({}), equal_to(False))
        assert_that(ConnectCallEvent.is_connect_event({'args': []}), equal_to(False))

    def test_is_connect_event_true(self):
        event = {
            'application': 'myapp',
            'args': ['red', 'dialed_from']
        }

        result = ConnectCallEvent.is_connect_event(event)

        assert_that(result, is_(True))

    def test_connect_event_originator_missing_event_args(self):
        assert_that(calling(ConnectCallEvent).with_args(channel=Mock(),
                                                        event={'application': 'myapp',
                                                               'args': ['red']},
                                                        ari=Mock(),
                                                        state_persistor=Mock()),
                    raises(InvalidConnectCallEvent))

    def test_connect_event_originator_wrong_originator(self):
        event = {
            'application': 'myapp',
            'args': ['red', 'dialed_from', 'channel-id']
        }
        ari = Mock()
        ari.channels.get.side_effect = HTTPError(response=Mock(status_code=404))

        assert_that(calling(ConnectCallEvent).with_args(channel=Mock(),
                                                        event=event,
                                                        ari=ari,
                                                        state_persistor=Mock()),
                    raises(InvalidConnectCallEvent))

    def test_connect_event_originator_valid(self):
        event = {
            'application': 'myapp',
            'args': ['red', 'dialed_from', 'channel-id']
        }
        ari = Mock()
        ari.channels.get.return_value = s.originator

        result = ConnectCallEvent(channel=Mock(),
                                  event=event,
                                  ari=ari,
                                  state_persistor=Mock())

        assert_that(result.originator_channel, equal_to(s.originator))
