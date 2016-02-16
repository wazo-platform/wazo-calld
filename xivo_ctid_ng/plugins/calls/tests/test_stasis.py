# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import json

from hamcrest import assert_that
from hamcrest import calling
from hamcrest import equal_to
from hamcrest import is_
from hamcrest import instance_of
from hamcrest import raises
from mock import Mock
from mock import sentinel as s
from requests.exceptions import HTTPError
from unittest import TestCase

from ..exceptions import InvalidCallEvent
from ..exceptions import InvalidConnectCallEvent
from ..exceptions import InvalidStartCallEvent
from ..stasis import CallEvent
from ..stasis import CallState
from ..stasis import ChannelCacheEntry
from ..stasis import ConnectCallEvent
from ..stasis import StatePersistor
from ..stasis import StartCallEvent
from ..stasis import StateFactory

ONE_HOUR = 3600


class TestChannelCacheEntry(TestCase):

    def test_to_dict(self):
        entry = ChannelCacheEntry(s.app, s.app_instance, s.state)

        assert_that(entry.to_dict(), equal_to({'app': s.app,
                                               'app_instance': s.app_instance,
                                               'state': s.state}))

    def test_from_dict(self):
        entry = ChannelCacheEntry.from_dict({'app': s.app,
                                             'app_instance': s.app_instance,
                                             'state': s.state})

        assert_that(entry.app, equal_to(s.app))
        assert_that(entry.app_instance, equal_to(s.app_instance))
        assert_that(entry.state, equal_to(s.state))


class TestStatePersistor(TestCase):

    def test_given_no_cache_when_get_then_raise_keyerror(self):
        ari = Mock()
        ari.asterisk.getGlobalVar.side_effect = HTTPError(response=Mock(status_code=404))
        persistor = StatePersistor(ari)

        assert_that(calling(persistor.get).with_args('unknown-channel-id'), raises(KeyError))

    def test_given_empty_cache_when_get_then_raise_keyerror(self):
        ari = Mock()
        ari.asterisk.getGlobalVar.return_value = {'value': ''}
        persistor = StatePersistor(ari)

        assert_that(calling(persistor.get).with_args('unknown-channel-id'), raises(KeyError))

    def test_given_valid_cache_when_get_unknown_channel_then_raise_keyerror(self):
        ari = Mock()
        ari.asterisk.getGlobalVar.return_value = {'value': '{}'}
        persistor = StatePersistor(ari)

        assert_that(calling(persistor.get).with_args('unknown-channel-id'), raises(KeyError))

    def test_given_valid_cache_when_get_existing_channel_then_return_entry(self):
        ari = Mock()
        ari.asterisk.getGlobalVar.return_value = {'value': json.dumps({'my-channel': {'app': 'myapp',
                                                                                      'app_instance': 'red',
                                                                                      'state': 'mystate'}})}
        persistor = StatePersistor(ari)

        result = persistor.get('my-channel')

        assert_that(result.state, equal_to('mystate'))

    def test_given_valid_empty_cache_when_remove_unknown_channel_then_nothing_happens(self):
        ari = Mock()
        ari.asterisk.getGlobalVar.return_value = {'value': '{}'}
        persistor = StatePersistor(ari)

        persistor.remove('unknown-channel')

        ari.asterisk.setGlobalVar.assert_called_once_with(variable=StatePersistor.global_var_name, value='{}')

    def test_given_valid_cache_when_remove_existing_channel_then_entry_removed(self):
        ari = Mock()
        ari.asterisk.getGlobalVar.return_value = {'value': json.dumps({'my-channel': {'app': 'myapp',
                                                                                      'app_instance': 'red',
                                                                                      'state': 'mystate'},
                                                                       'my-other-channel': {'app': 'myapp',
                                                                                            'app_instance': 'red',
                                                                                            'state': 'mystate'}})}
        persistor = StatePersistor(ari)

        persistor.remove('my-channel')

        expected_cache = json.dumps({'my-other-channel': {'app': 'myapp',
                                                          'app_instance': 'red',
                                                          'state': 'mystate'}})
        ari.asterisk.setGlobalVar.assert_called_once_with(variable=StatePersistor.global_var_name, value=expected_cache)

    def test_given_channel_not_found_when_upsert_channel_then_entry_inserted(self):
        entry = Mock()
        entry.to_dict.return_value = 'my-entry'
        ari = Mock()
        ari.asterisk.getGlobalVar.return_value = {'value': json.dumps({'my-other-channel': 'other-entry'})}
        persistor = StatePersistor(ari)

        persistor.upsert('my-channel', entry)

        expected_cache = json.dumps({'my-channel': 'my-entry', 'my-other-channel': 'other-entry'})
        ari.asterisk.setGlobalVar.assert_called_once_with(variable=StatePersistor.global_var_name, value=expected_cache)

    def test_given_existing_channel_when_upsert_then_entry_updated(self):
        entry = Mock()
        entry.to_dict.return_value = 'new-entry'
        ari = Mock()
        ari.asterisk.getGlobalVar.return_value = {'value': json.dumps({'my-channel': 'old-entry'})}
        persistor = StatePersistor(ari)

        persistor.upsert('my-channel', entry)

        expected_cache = json.dumps({'my-channel': 'new-entry'})
        ari.asterisk.setGlobalVar.assert_called_once_with(variable=StatePersistor.global_var_name, value=expected_cache)


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


class TestStateFactory(TestCase):

    def test_make_before_set_dependencies(self):
        factory = StateFactory()

        assert_that(calling(factory.make).with_args('state-name'), raises(AssertionError))

    def test_make_unknown_state(self):
        factory = StateFactory()
        factory.set_dependencies(ari=Mock(), stat_sender=Mock())

        assert_that(calling(factory.make).with_args('state-name'), raises(KeyError))

    def test_make_valid_state(self):
        factory = StateFactory()
        factory.set_dependencies(ari=Mock(), stat_sender=Mock())

        @factory.state
        class MyState(CallState):
            name = 'my-state'

        assert_that(factory.make('my-state'), instance_of(MyState))
