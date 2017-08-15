# -*- coding: utf-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import (
    assert_that,
    contains,
    equal_to,
    not_,
    none,
    has_entries,
    has_item,
)
from xivo_test_helpers import until

from .test_api.auth import MockUserToken
from .test_api.base import IntegrationTest
from .test_api.chat import new_chat_message
from .test_api.chat import new_user_chat_message
from .test_api.chat import new_uuid_str
from .test_api.constants import VALID_TOKEN
from .test_api.constants import XIVO_UUID


class TestCreateChat(IntegrationTest):

    asset = 'mongooseim'

    @classmethod
    def setUpClass(cls):
        super(TestCreateChat, cls).setUpClass()
        cls.wait_for_ctid_ng_to_connect_to_bus()
        cls.wait_for_mongooseim_to_connect_to_db()

    def setUp(self):
        super(TestCreateChat, self).setUp()
        self.events = self.bus.accumulator(routing_key='chat.message.#')
        self.chat_msg = new_chat_message()

    def test_create_chat_with_correct_values(self):
        result = self.ctid_ng.post_chat_result(self.chat_msg, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(204))
        self._assert_chat_msg_sent_on_bus()

    def test_create_chat_with_different_to_xivo_uuid(self):
        self.chat_msg.to_xivo_uuid = new_uuid_str()

        result = self.ctid_ng.post_chat_result(self.chat_msg, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(204))
        self._assert_chat_msg_sent_on_bus()

    def _assert_chat_msg_sent_on_bus(self):
        def assert_function():
            destination = [self.chat_msg.to_xivo_uuid or XIVO_UUID, self.chat_msg.to]
            assert_that(self.events.accumulate(), has_item(equal_to({
                'name': 'chat_message_event',
                'origin_uuid': XIVO_UUID,
                'required_acl': 'events.chat.message.{}.{}'.format(*destination),
                'data': {
                    'alias': self.chat_msg.alias,
                    'to': destination,
                    'from': [XIVO_UUID, self.chat_msg.from_],
                    'msg': self.chat_msg.content,
                }
            })))
        until.assert_(assert_function, tries=5)


class TestUserCreateChat(IntegrationTest):

    asset = 'mongooseim'

    @classmethod
    def setUpClass(cls):
        super(TestUserCreateChat, cls).setUpClass()
        cls.wait_for_ctid_ng_to_connect_to_bus()

    def setUp(self):
        super(TestUserCreateChat, self).setUp()
        self.events = self.bus.accumulator(routing_key='chat.message.#')
        self.token_id = 'my-token'
        self.token_user_uuid = new_uuid_str()
        self.auth.set_token(MockUserToken('my-token', self.token_user_uuid))

    def test_create_chat_with_correct_values(self):
        message = new_user_chat_message()
        result = self.ctid_ng.post_user_chat_result(message, token=self.token_id)

        assert_that(result.status_code, equal_to(204))
        self._assert_chat_msg_sent_on_bus(message)

    def _assert_chat_msg_sent_on_bus(self, message):
        def assert_function():
            assert_that(self.events.accumulate(), has_item(equal_to({
                'name': 'chat_message_event',
                'origin_uuid': XIVO_UUID,
                'required_acl': 'events.chat.message.{}.{}'.format(XIVO_UUID, message.to),
                'data': {
                    'alias': message.alias,
                    'to': [XIVO_UUID, message.to],
                    'from': [XIVO_UUID, self.token_user_uuid],
                    'msg': message.content,
                }
            })))
        until.assert_(assert_function, tries=5)

    def test_get_chats(self):
        message1 = new_user_chat_message()
        message2 = new_user_chat_message()
        self.ctid_ng.post_user_chat(message1, token=self.token_id)
        self.ctid_ng.post_user_chat(message2, token=self.token_id)

        result = self.ctid_ng.get_user_chat(token=self.token_id)
        assert_that(result['items'], contains(
            has_entries(date=not_(none()),
                        source_user_uuid=self.token_user_uuid,
                        source_server_uuid=XIVO_UUID,
                        destination_user_uuid=None,
                        destination_server_uuid=None,
                        direction='sent',
                        msg=message1.content),
            has_entries(date=not_(none()),
                        source_user_uuid=self.token_user_uuid,
                        source_server_uuid=XIVO_UUID,
                        destination_user_uuid=None,
                        destination_server_uuid=None,
                        direction='sent',
                        msg=message2.content),
        ))

    def test_get_chats_with_participant(self):
        user2 = new_uuid_str()
        message1 = new_user_chat_message()
        message1.to = user2
        message2 = new_chat_message()
        message2.from_ = user2
        message2.to = self.token_user_uuid
        message3 = new_user_chat_message()
        self.ctid_ng.post_user_chat(message1, token=self.token_id)
        self.ctid_ng.post_chat(message2, token=self.token_id)
        self.ctid_ng.post_user_chat(message3, token=self.token_id)

        result = self.ctid_ng.get_user_chat(token=self.token_id,
                                            participant_user_uuid=user2,
                                            participant_server_uuid=XIVO_UUID)
        assert_that(result['items'], contains(
            has_entries(date=not_(none()),
                        source_user_uuid=self.token_user_uuid,
                        source_server_uuid=XIVO_UUID,
                        destination_user_uuid=message1.to,
                        destination_server_uuid=XIVO_UUID,
                        direction='sent',
                        msg=message1.content),
            has_entries(date=not_(none()),
                        source_user_uuid=message2.from_,
                        source_server_uuid=XIVO_UUID,
                        destination_user_uuid=self.token_user_uuid,
                        destination_server_uuid=XIVO_UUID,
                        direction='received',
                        msg=message2.content),
        ))

    def test_get_chats_with_limit(self):
        message1 = new_user_chat_message()
        message1.content = 'message1'
        message2 = new_user_chat_message()
        message2.content = 'message2'
        self.ctid_ng.post_user_chat(message1, token=self.token_id)
        self.ctid_ng.post_user_chat(message2, token=self.token_id)

        result = self.ctid_ng.get_user_chat(token=self.token_id, limit=1)
        assert_that(result['items'], contains(
            has_entries(msg=message2.content)
        ))
