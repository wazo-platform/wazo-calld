# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
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

from ..exceptions import InvalidCallEvent
from ..exceptions import InvalidConnectCallEvent
from ..exceptions import InvalidStartCallEvent
from ..event import CallEvent
from ..event import ConnectCallEvent
from ..event import StartCallEvent

ONE_HOUR = 3600


class TestCallEvent(TestCase):

    def test_duration(self):
        state_persistor = Mock()
        state_persistor.get.return_value = Mock(app='my-app', app_instance='red')
        event = CallEvent(channel=Mock(json={'creationtime': '2016-02-16T13:31:00Z'}),
                          event={'timestamp': '2016-02-16T13:32:00Z'},
                          state_persistor=state_persistor)

        result = event.duration()

        assert_that(result, equal_to(60))

    def test_duration_different_timezones(self):
        state_persistor = Mock()
        state_persistor.get.return_value = Mock(app='my-app', app_instance='red')
        event = CallEvent(channel=Mock(json={'creationtime': '2016-02-16T13:31:00+0100'}),
                          event={'timestamp': '2016-02-16T13:31:00-0500'},
                          state_persistor=state_persistor)

        result = event.duration()

        assert_that(result, equal_to(6 * ONE_HOUR))

    def test_app_app_instance(self):
        state_persistor = Mock()
        state_persistor.get.return_value = Mock(app='my-app', app_instance='red')
        event = CallEvent(channel=Mock(),
                          event={},
                          state_persistor=state_persistor)

        assert_that(event.app, equal_to('my-app'))
        assert_that(event.app_instance, equal_to('red'))

    def test_app_app_instance_unknown_channel(self):
        state_persistor = Mock()
        state_persistor.get.side_effect = KeyError
        assert_that(calling(CallEvent).with_args(channel=Mock(),
                                                 event={},
                                                 state_persistor=state_persistor),
                    raises(InvalidCallEvent))


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
