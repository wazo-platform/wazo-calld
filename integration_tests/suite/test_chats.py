# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import equal_to
from hamcrest import has_item
from xivo_test_helpers import until

from .test_api.auth import MockUserToken
from .test_api.base import IntegrationTest
from .test_api.chat import new_chat_message
from .test_api.chat import new_user_chat_message
from .test_api.chat import new_uuid_str
from .test_api.constants import VALID_TOKEN
from .test_api.constants import XIVO_UUID


class TestCreateChat(IntegrationTest):

    asset = 'basic_rest'

    @classmethod
    def setUpClass(cls):
        super(TestCreateChat, cls).setUpClass()
        cls.wait_for_ctid_ng_to_connect_to_bus()

    def setUp(self):
        super(TestCreateChat, self).setUp()
        self.bus.listen_events(routing_key='chat.message.#')
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
            assert_that(self.bus.events(), has_item(equal_to({
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

    asset = 'basic_rest'

    @classmethod
    def setUpClass(cls):
        super(TestUserCreateChat, cls).setUpClass()
        cls.wait_for_ctid_ng_to_connect_to_bus()

    def setUp(self):
        super(TestUserCreateChat, self).setUp()
        self.bus.listen_events(routing_key='chat.message.#')
        self.chat_msg = new_user_chat_message()
        self.token_id = 'my-token'
        self.token_user_uuid = 'my-user-uuid'
        self.auth.set_token(MockUserToken('my-token', self.token_user_uuid))

    def test_create_chat_with_correct_values(self):
        result = self.ctid_ng.post_user_chat_result(self.chat_msg, token=self.token_id)

        assert_that(result.status_code, equal_to(204))
        self._assert_chat_msg_sent_on_bus()

    def _assert_chat_msg_sent_on_bus(self):
        def assert_function():
            assert_that(self.bus.events(), has_item(equal_to({
                'name': 'chat_message_event',
                'origin_uuid': XIVO_UUID,
                'required_acl': 'events.chat.message.{}.{}'.format(XIVO_UUID, self.chat_msg.to),
                'data': {
                    'alias': self.chat_msg.alias,
                    'to': [XIVO_UUID, self.chat_msg.to],
                    'from': [XIVO_UUID, self.token_user_uuid],
                    'msg': self.chat_msg.content,
                }
            })))
        until.assert_(assert_function, tries=5)
