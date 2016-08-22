# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import contains_string
from hamcrest import equal_to
from hamcrest import has_item
from hamcrest import has_entries
from hamcrest import instance_of

from xivo_test_helpers import until

from .test_api.auth import MockUserToken
from .test_api.base import IntegrationTest
from .test_api.presence import new_user_presence_message
from .test_api.presence import new_user_me_presence_message
from .test_api.constants import VALID_TOKEN
from .test_api.constants import XIVO_UUID


class TestGetUserPresence(IntegrationTest):

    asset = 'basic_rest'

    @classmethod
    def setUpClass(cls):
        super(TestGetUserPresence, cls).setUpClass()

    def setUp(self):
        super(TestGetUserPresence, self).setUp()
        self.token_user_uuid = 'my-user-uuid'

    def test_get_presence_with_correct_values(self):
        result = self.ctid_ng.get_user_presence_result(self.token_user_uuid, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(200))
        assert_that(result.json(), has_entries({'user_uuid': contains_string(self.token_user_uuid),
                                                'xivo_uuid': contains_string(XIVO_UUID),
                                                'presence': contains_string('available')}))


class TestGetUserMePresence(IntegrationTest):

    asset = 'basic_rest'

    @classmethod
    def setUpClass(cls):
        super(TestGetUserMePresence, cls).setUpClass()

    def setUp(self):
        super(TestGetUserMePresence, self).setUp()
        self.token_id = 'my-token'
        self.token_user_uuid = 'my-user-uuid'
        self.auth.set_token(MockUserToken('my-token', self.token_user_uuid))

    def test_get_presence_with_correct_values(self):
        result = self.ctid_ng.get_user_me_presence_result(token=self.token_id)

        assert_that(result.status_code, equal_to(200))
        assert_that(result.json(), has_entries({'user_uuid': contains_string(self.token_user_uuid),
                                                'xivo_uuid': contains_string(XIVO_UUID),
                                                'presence': contains_string('available')}))


class TestUpdateUserPresence(IntegrationTest):

    asset = 'basic_rest'

    @classmethod
    def setUpClass(cls):
        super(TestUpdateUserPresence, cls).setUpClass()
        cls.wait_for_ctid_ng_to_connect_to_bus()

    def setUp(self):
        super(TestUpdateUserPresence, self).setUp()
        self.bus.listen_events(routing_key='status.user')
        self.presence_msg = new_user_presence_message()
        self.token_user_uuid = 'my-user-uuid'

    def test_create_presence_with_correct_values(self):
        result = self.ctid_ng.put_user_presence_result(self.presence_msg, self.token_user_uuid, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(204))
        self._assert_presence_msg_sent_on_bus()

    def _assert_presence_msg_sent_on_bus(self):
        def assert_function():
            assert_that(self.bus.events(), has_item(equal_to({
                'name': 'user_status_update',
                'origin_uuid': XIVO_UUID,
                'required_acl': 'events.statuses.users',
                'data': {
                    'user_uuid': self.token_user_uuid,
                    'status': 'available',
                }
            })))
        until.assert_(assert_function, tries=5)


class TestUserMeUpdatePresence(IntegrationTest):

    asset = 'basic_rest'

    @classmethod
    def setUpClass(cls):
        super(TestUserMeUpdatePresence, cls).setUpClass()
        cls.wait_for_ctid_ng_to_connect_to_bus()

    def setUp(self):
        super(TestUserMeUpdatePresence, self).setUp()
        self.bus.listen_events(routing_key='status.user')
        self.presence_msg = new_user_me_presence_message()
        self.token_id = 'my-token'
        self.token_user_uuid = 'my-user-uuid'
        self.auth.set_token(MockUserToken('my-token', self.token_user_uuid))

    def test_create_presence_with_correct_values(self):
        result = self.ctid_ng.put_user_me_presence_result(self.presence_msg, token=self.token_id)

        assert_that(result.status_code, equal_to(204))
        self._assert_presence_msg_sent_on_bus()

    def _assert_presence_msg_sent_on_bus(self):
        def assert_function():
            assert_that(self.bus.events(), has_item(equal_to({
                'name': 'user_status_update',
                'origin_uuid': XIVO_UUID,
                'required_acl': 'events.statuses.users',
                'data': {
                    'user_uuid': self.token_user_uuid,
                    'status': 'available',
                }
            })))
        until.assert_(assert_function, tries=5)


class TestGetLinePresence(IntegrationTest):

    asset = 'basic_rest'

    @classmethod
    def setUpClass(cls):
        super(TestGetLinePresence, cls).setUpClass()

    def setUp(self):
        super(TestGetLinePresence, self).setUp()

    def test_get_presence_with_correct_values(self):
        line_id = 'valid-id'
        result = self.ctid_ng.get_line_presence_result(line_id, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(200))
        assert_that(result.json(), has_entries({'line_id': contains_string(line_id),
                                                'xivo_uuid': contains_string(XIVO_UUID),
                                                'presence': instance_of(int)}))
