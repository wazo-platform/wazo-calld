# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import json

from hamcrest import assert_that
from hamcrest import calling
from hamcrest import equal_to
from hamcrest import raises
from mock import Mock
from mock import sentinel as s
from requests.exceptions import HTTPError
from unittest import TestCase

from ..state_persistor import ChannelCacheEntry
from ..state_persistor import StatePersistor


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
