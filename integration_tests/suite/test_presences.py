# -*- coding: utf-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
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
        self.websocketd.set_get_presence(presence='dnd')
        result = self.ctid_ng.get_user_presence_result(self.token_user_uuid, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(200))
        assert_that(result.json(), has_entries({'user_uuid': contains_string(self.token_user_uuid),
                                                'xivo_uuid': contains_string(XIVO_UUID),
                                                'presence': contains_string('dnd')}))

    def test_get_presence_when_websocketd_nok(self):
        self.websocketd.set_get_presence(code=1234)
        result = self.ctid_ng.get_user_presence_result(self.token_user_uuid, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))

    def test_get_presence_when_websocketd_unauthorized(self):
        self.websocketd.set_get_presence(code=401)
        result = self.ctid_ng.get_user_presence_result(self.token_user_uuid, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))

    def test_get_presence_with_unknown_values(self):
        self.websocketd.set_get_presence(code=404)
        result = self.ctid_ng.get_user_presence_result('unknown-user', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(404))

    def test_get_presence_with_unknown_xivo_uuid(self):
        result = self.ctid_ng.get_user_presence_result(self.token_user_uuid,
                                                       xivo_uuid='unknown',
                                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))

    def test_get_presence_with_an_unregistered_wazo_auth(self):
        result = self.ctid_ng.get_user_presence_result(self.token_user_uuid,
                                                       xivo_uuid='582fbd45-73a3-41dd-9079-4c6d16fe1aad',
                                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))
        missing_service = result.json()['details']['service']
        assert_that(missing_service, equal_to('wazo-auth'))

    def test_get_presence_with_invalid_credentials(self):
        result = self.ctid_ng.get_user_presence_result(self.token_user_uuid,
                                                       xivo_uuid='51400e55-2dc3-4cfc-a2f2-a4d4f0f8b217',
                                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(502))

    def test_get_presence_with_an_unregistered_xivo_ctid_ng(self):
        result = self.ctid_ng.get_user_presence_result(self.token_user_uuid,
                                                       xivo_uuid='196e42b9-bbfe-4c03-b3d4-684dffd01603',
                                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))
        missing_service = result.json()['details']['service']
        assert_that(missing_service, equal_to('xivo-ctid-ng'))

    def test_get_presence_with_401_from_the_remote_ctid_ng(self):
        result = self.ctid_ng.get_user_presence_result(self.token_user_uuid,
                                                       xivo_uuid='04b0087e-1661-4a42-8181-4b61e198204d',
                                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(502))

    def test_get_presence_with_404_from_the_remote_ctid_ng(self):
        result = self.ctid_ng.get_user_presence_result('unknown',
                                                       xivo_uuid='5720ee16-61cc-412e-93c9-ae06fa0be845',
                                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(404))

    def test_get_presence_with_a_result_from_the_remote_ctid_ng(self):
        user_uuid, xivo_uuid = 'working', '5720ee16-61cc-412e-93c9-ae06fa0be845'
        result = self.ctid_ng.get_user_presence_result(user_uuid,
                                                       xivo_uuid=xivo_uuid,
                                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(200))
        assert_that(result.json(), has_entries({'user_uuid': contains_string(user_uuid),
                                                'xivo_uuid': contains_string(xivo_uuid),
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
        self.websocketd.set_get_presence(presence='available')
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
        self.events = self.bus.accumulator(routing_key='status.user')
        self.presence_msg = new_user_presence_message()
        self.token_user_uuid = 'my-user-uuid'

    def test_create_presence_with_correct_values(self):
        result = self.ctid_ng.put_user_presence_result(self.presence_msg, self.token_user_uuid, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(204))
        self._assert_presence_msg_sent_on_bus()

    def _assert_presence_msg_sent_on_bus(self):
        def assert_function():
            assert_that(self.events.accumulate(), has_item(equal_to({
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
        self.events = self.bus.accumulator(routing_key='status.user')
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
            assert_that(self.events.accumulate(), has_item(equal_to({
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
        line_id = 42
        result = self.ctid_ng.get_line_presence_result(line_id, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(200))
        assert_that(result.json(), has_entries({'line_id': equal_to(int(line_id)),
                                                'xivo_uuid': contains_string(XIVO_UUID),
                                                'presence': instance_of(int)}))

    def test_get_presence_with_unknown_values(self):
        line_id = 6
        result = self.ctid_ng.get_line_presence_result(line_id, token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(404))

    def test_get_presence_with_unknown_xivo_uuid(self):
        result = self.ctid_ng.get_line_presence_result(42,
                                                       xivo_uuid='unknown',
                                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(400))

    def test_get_presence_with_an_unregistered_wazo_auth(self):
        result = self.ctid_ng.get_line_presence_result(42,
                                                       xivo_uuid='582fbd45-73a3-41dd-9079-4c6d16fe1aad',
                                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))
        missing_service = result.json()['details']['service']
        assert_that(missing_service, equal_to('wazo-auth'))

    def test_get_presence_with_invalid_credentials(self):
        result = self.ctid_ng.get_line_presence_result(42,
                                                       xivo_uuid='51400e55-2dc3-4cfc-a2f2-a4d4f0f8b217',
                                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(502))

    def test_get_presence_with_an_unregistered_xivo_ctid_ng(self):
        result = self.ctid_ng.get_line_presence_result(42,
                                                       xivo_uuid='196e42b9-bbfe-4c03-b3d4-684dffd01603',
                                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(503))
        missing_service = result.json()['details']['service']
        assert_that(missing_service, equal_to('xivo-ctid-ng'))

    def test_get_presence_with_401_from_the_remote_ctid_ng(self):
        result = self.ctid_ng.get_line_presence_result(42,
                                                       xivo_uuid='04b0087e-1661-4a42-8181-4b61e198204d',
                                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(502))

    def test_get_presence_with_404_from_the_remote_ctid_ng(self):
        result = self.ctid_ng.get_line_presence_result(13,
                                                       xivo_uuid='5720ee16-61cc-412e-93c9-ae06fa0be845',
                                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(404))

    def test_get_presence_with_a_result_from_the_remote_ctid_ng(self):
        line_id, xivo_uuid = 42, '5720ee16-61cc-412e-93c9-ae06fa0be845'
        result = self.ctid_ng.get_line_presence_result(line_id,
                                                       xivo_uuid=xivo_uuid,
                                                       token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(200))
        assert_that(result.json(), has_entries({'line_id': equal_to(42),
                                                'xivo_uuid': contains_string(xivo_uuid),
                                                'presence': equal_to(8)}))
