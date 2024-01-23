# Copyright 2016-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from io import BytesIO
from unittest import TestCase
from unittest.mock import Mock

from hamcrest import (
    assert_that,
    calling,
    contains_exactly,
    empty,
    equal_to,
    has_key,
    not_,
    raises,
)

from ..storage import _MessageInfoParser, _VoicemailFolder, _VoicemailMessagesCache


class TestMessageInfoParser(TestCase):
    def setUp(self):
        self.result = {}
        self.parser = _MessageInfoParser()

    def test_parse(self):
        content = b'''
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
callerchan=PJSIP/xivo64-00000000
callerid="Etienne" <101>
origdate=Thu Nov  3 07:11:59 PM UTC 2016
origtime=1478200319
category=
msg_id=1478200319-00000000
flag=
duration=12
'''  # noqa: W291
        result = self._parse(content)
        expected = {
            'id': '1478200319-00000000',
            'caller_id_name': 'Etienne',
            'caller_id_num': '101',
            'timestamp': 1478200319,
            'duration': 12,
        }
        assert_that(result, equal_to(expected))

    def test_parse_with_spaces(self):
        content = b'''
;
; Message Information file
;
[message]
origmailbox = 1001
context   = user
macrocontext   =
exten=     voicemail
rdnis = 1001
priority=7
callerchan   =    PJSIP/xivo64-00000000
   callerid = "Etienne" <101>
 origdate = Thu Nov  3 07:11:59 PM UTC 2016
origtime=  1478200319
category=
msg_id=1478200319-00000000
flag=
duration= 12
'''  # noqa: W291
        result = self._parse(content)
        expected = {
            'id': '1478200319-00000000',
            'caller_id_name': 'Etienne',
            'caller_id_num': '101',
            'timestamp': 1478200319,
            'duration': 12,
        }
        assert_that(result, equal_to(expected))

    def test_parse_missing_field(self):
        content = b'''
callerid="Etienne" <101>
origtime=1478200319
msg_id=1478200319-00000000
'''  # noqa: W291
        assert_that(calling(self._parse).with_args(content), raises(Exception))

    def test_parse_callerid_unknown(self):
        # happens when app_voicemail write a message with no caller ID information
        self.parser._parse_callerid(b'Unknown', self.result)

        assert_that(
            self.result, equal_to({'caller_id_name': None, 'caller_id_num': None})
        )

    def test_parse_callerid_incomplete(self):
        self.parser._parse_callerid(b'1234', self.result)

        assert_that(
            self.result, equal_to({'caller_id_name': None, 'caller_id_num': '1234'})
        )

    def _parse(self, content):
        return self.parser.parse(BytesIO(content))


class TestVoicemailMessagesCache(TestCase):
    def setUp(self):
        self.number = '1001'
        self.context = 'internal'
        self.cache_key = (self.number, self.context)
        self.storage = Mock()
        self.storage.get_voicemail_info.return_value = {
            'folders': [],
        }
        self.cache = _VoicemailMessagesCache(self.storage)
        self.folder1 = _VoicemailFolder(1, b'Folder1')
        self.folder2 = _VoicemailFolder(1, b'Folder2')
        self.message_info1 = {
            'id': 'msg1',
            'folder': self.folder1,
        }
        self.message_info2 = {
            'id': 'msg1',
            'folder': self.folder2,
        }

    def test_diff_when_message_created(self):
        self.storage.get_voicemail_info.return_value = {
            'folders': [
                {
                    'messages': [self.message_info1],
                }
            ],
        }

        diff = self.cache.get_diff(self.number, self.context)

        assert_that(diff.created_messages, contains_exactly(self.message_info1))
        assert_that(diff.updated_messages, empty())
        assert_that(diff.deleted_messages, empty())

    def test_diff_when_message_updated(self):
        self.storage.get_voicemail_info.return_value = {
            'folders': [
                {
                    'messages': [self.message_info2],
                }
            ],
        }
        self.cache._cache[self.cache_key] = {
            self.message_info1['id']: self.message_info1,
        }

        diff = self.cache.get_diff(self.number, self.context)

        assert_that(diff.created_messages, empty())
        assert_that(diff.updated_messages, contains_exactly(self.message_info2))
        assert_that(diff.deleted_messages, empty())

    def test_diff_when_message_deleted(self):
        self.storage.get_voicemail_info.return_value = {
            'folders': [],
        }
        self.cache._cache[self.cache_key] = {
            self.message_info1['id']: self.message_info1,
        }

        diff = self.cache.get_diff(self.number, self.context)

        assert_that(diff.created_messages, empty())
        assert_that(diff.updated_messages, empty())
        assert_that(diff.deleted_messages, contains_exactly(self.message_info1))

    def test_diff_twice_in_a_row(self):
        self.storage.get_voicemail_info.return_value = {
            'folders': [
                {
                    'messages': [self.message_info1],
                }
            ],
        }

        diff1 = self.cache.get_diff(self.number, self.context)
        diff2 = self.cache.get_diff(self.number, self.context)

        assert_that(diff1.created_messages, contains_exactly(self.message_info1))
        assert_that(diff2.created_messages, empty())

    def test_cache_cleanup(self):
        key1 = ('1001', 'default')
        key2 = ('1002', 'default')
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

        assert_that(cache._cache, not_(has_key(self.cache_key)))
        self.storage.list_voicemails_number_and_context.assert_called_once_with()
