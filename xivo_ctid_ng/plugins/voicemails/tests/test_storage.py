# -*- coding: utf-8 -*-
# Copyright 2016 Proformatique Inc.
# SPDX-License-Identifier: GPL-3.0+

from mock import Mock
from hamcrest import assert_that
from hamcrest import calling
from hamcrest import contains
from hamcrest import empty
from hamcrest import equal_to
from hamcrest import has_key
from hamcrest import not_
from hamcrest import raises
from StringIO import StringIO
from unittest import TestCase

from ..storage import _MessageInfoParser
from ..storage import _VoicemailMessagesCache
from ..storage import _VoicemailFolder


class TestMessageInfoParser(TestCase):

    def setUp(self):
        self.result = {}
        self.parser = _MessageInfoParser()

    def test_parse(self):
        content = '''
;
; Message Information file
;
[message]
origmailbox=1001
context=user
macrocontext=
exten=voicemail
rdnis=1001
priority=7
callerchan=SIP/xivo64-00000000
callerid="Etienne" <101>
origdate=Thu Nov  3 07:11:59 PM UTC 2016
origtime=1478200319
category=
msg_id=1478200319-00000000
flag=
duration=12
'''
        result = self._parse(content)
        expected = {
            u'id': u'1478200319-00000000',
            u'caller_id_name': u'Etienne',
            u'caller_id_num': u'101',
            u'timestamp': 1478200319,
            u'duration': 12,
        }
        assert_that(result, equal_to(expected))

    def test_parse_missing_field(self):
        content = '''
callerid="Etienne" <101>
origtime=1478200319
msg_id=1478200319-00000000
'''
        assert_that(calling(self._parse).with_args(content), raises(Exception))

    def test_parse_callerid_unknown(self):
        # happens when app_voicemail write a message with no caller ID information
        self.parser._parse_callerid('Unknown', self.result)

        assert_that(self.result, equal_to({u'caller_id_name': None, u'caller_id_num': None}))

    def test_parse_callerid_incomplete(self):
        self.parser._parse_callerid('1234', self.result)

        assert_that(self.result, equal_to({u'caller_id_name': None, u'caller_id_num': u'1234'}))

    def _parse(self, content):
        return self.parser.parse(StringIO(content))


class TestVoicemailMessagesCache(TestCase):

    def setUp(self):
        self.number = u'1001'
        self.context = u'internal'
        self.cache_key = (self.number, self.context)
        self.storage = Mock()
        self.storage.get_voicemail_info.return_value = {
            u'folders': [],
        }
        self.cache = _VoicemailMessagesCache(self.storage)
        self.folder1 = _VoicemailFolder(1, 'Folder1')
        self.folder2 = _VoicemailFolder(1, 'Folder2')
        self.message_info1 = {
            u'id': u'msg1',
            u'folder': self.folder1,
        }
        self.message_info2 = {
            u'id': u'msg1',
            u'folder': self.folder2,
        }

    def test_diff_when_message_created(self):
        self.storage.get_voicemail_info.return_value = {
            u'folders': [{
                u'messages': [self.message_info1],
            }],
        }

        diff = self.cache.get_diff(self.number, self.context)

        assert_that(diff.created_messages, contains(self.message_info1))
        assert_that(diff.updated_messages, empty())
        assert_that(diff.deleted_messages, empty())

    def test_diff_when_message_updated(self):
        self.storage.get_voicemail_info.return_value = {
            u'folders': [{
                u'messages': [self.message_info2],
            }],
        }
        self.cache._cache[self.cache_key] = {
            self.message_info1[u'id']: self.message_info1,
        }

        diff = self.cache.get_diff(self.number, self.context)

        assert_that(diff.created_messages, empty())
        assert_that(diff.updated_messages, contains(self.message_info2))
        assert_that(diff.deleted_messages, empty())

    def test_diff_when_message_deleted(self):
        self.storage.get_voicemail_info.return_value = {
            u'folders': [],
        }
        self.cache._cache[self.cache_key] = {
            self.message_info1[u'id']: self.message_info1,
        }

        diff = self.cache.get_diff(self.number, self.context)

        assert_that(diff.created_messages, empty())
        assert_that(diff.updated_messages, empty())
        assert_that(diff.deleted_messages, contains(self.message_info1))

    def test_diff_twice_in_a_row(self):
        self.storage.get_voicemail_info.return_value = {
            u'folders': [{
                u'messages': [self.message_info1],
            }],
        }

        diff1 = self.cache.get_diff(self.number, self.context)
        diff2 = self.cache.get_diff(self.number, self.context)

        assert_that(diff1.created_messages, contains(self.message_info1))
        assert_that(diff2.created_messages, empty())

    def test_cache_cleanup(self):
        key1 = (u'1001', u'default')
        key2 = (u'1002', u'default')
        self.storage.list_voicemails_number_and_context.return_value = [key1]
        cache = _VoicemailMessagesCache(self.storage, 0)
        cache._cache = {
            key1: {},
            key2: {},
        }

        cache.get_diff(self.number, self.context)

        assert_that(cache._cache, has_key(key1))
        assert_that(cache._cache, not_(has_key(key2)))

    def test_cache_is_cleaned_periodically(self):
        cache = _VoicemailMessagesCache(self.storage, 1)
        cache._cache[self.cache_key] = {}
        self.storage.list_voicemails_number_and_context.return_value = []

        cache.get_diff(self.number, self.context)

        assert_that(cache._cache, has_key(self.cache_key))

        cache.get_diff(self.number, self.context)

        print cache._cache
        assert_that(cache._cache, not_(has_key(self.cache_key)))
        self.storage.list_voicemails_number_and_context.assert_called_once_with()
