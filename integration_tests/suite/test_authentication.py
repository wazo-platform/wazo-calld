# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that
from hamcrest import contains_string
from hamcrest import equal_to

from .helpers.base import IntegrationTest
from .helpers.chat import new_chat_message, new_user_chat_message
from .helpers.constants import INVALID_ACL_TOKEN, VALID_TOKEN
from .helpers.wait_strategy import CtidNgUpWaitStrategy


class TestAuthentication(IntegrationTest):

    asset = 'basic_rest'

    def test_no_auth_gives_401(self):
        result = self.ctid_ng.get_call_result('my-call', token=None)

        assert_that(result.status_code, equal_to(401))

    def test_invalid_auth_gives_401(self):
        result = self.ctid_ng.get_call_result('my-call', token='invalid-token')

        assert_that(result.status_code, equal_to(401))

    def test_invalid_acl_gives_401(self):
        result = self.ctid_ng.get_call_result('my-call', token=INVALID_ACL_TOKEN)

        assert_that(result.status_code, equal_to(401))

    def test_valid_auth_gives_result(self):
        result = self.ctid_ng.get_call_result('my-call', token=VALID_TOKEN)

        assert_that(result.status_code, equal_to(404))


class TestAuthenticationError(IntegrationTest):

    asset = 'no_auth_server'
    wait_strategy = CtidNgUpWaitStrategy()

    def test_no_auth_server_gives_503(self):
        result = self.ctid_ng.get_call_result('my-call', token=None)

        assert_that(result.status_code, equal_to(503))
        assert_that(result.json()['message'], contains_string('Authentication server'))


class TestAuthenticationCoverage(IntegrationTest):

    asset = 'basic_rest'

    def test_auth_on_list_calls(self):
        result = self.ctid_ng.get_calls_result()

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_list_user_calls(self):
        result = self.ctid_ng.get_users_me_calls_result()

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_get_call(self):
        result = self.ctid_ng.get_call_result('my-call')

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_new_call(self):
        result = self.ctid_ng.post_call_result(source=None, priority=None, extension=None, context=None)

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_new_user_call(self):
        result = self.ctid_ng.post_user_me_call_result(body={})

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_hangup(self):
        result = self.ctid_ng.delete_call_result('my-call')

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_user_hangup(self):
        result = self.ctid_ng.delete_user_me_call_result('my-call')

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_new_chat(self):
        result = self.ctid_ng.post_chat_result(new_chat_message())

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_new_user_chat(self):
        result = self.ctid_ng.post_user_chat_result(new_user_chat_message())

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_list_user_transfer(self):
        result = self.ctid_ng.get_users_me_transfers_result()

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_get_transfer(self):
        result = self.ctid_ng.get_transfer_result('my-transfer')

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_new_transfer(self):
        result = self.ctid_ng.post_transfer_result(body={})

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_new_user_transfer(self):
        result = self.ctid_ng.post_user_transfer_result(body={})

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_transfer_cancel(self):
        result = self.ctid_ng.delete_transfer_result('my-transfer')

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_cancel_user_transfer(self):
        result = self.ctid_ng.delete_users_me_transfer_result('my-transfer')

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_transfer_complete(self):
        result = self.ctid_ng.put_complete_transfer_result('my-transfer')

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_complete_user_transfer(self):
        result = self.ctid_ng.put_users_me_complete_transfer_result('my-transfer')

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_get_voicemail(self):
        result = self.ctid_ng.get_voicemail_result(1)

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_get_user_voicemail(self):
        result = self.ctid_ng.get_user_me_voicemail_result()

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_get_voicemail_folder(self):
        result = self.ctid_ng.get_voicemail_folder_result(1, 1)

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_get_user_voicemail_folder(self):
        result = self.ctid_ng.get_user_me_voicemail_folder_result(1)

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_delete_voicemail_message(self):
        result = self.ctid_ng.delete_voicemail_message_result(1, '42')

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_delete_user_voicemail_message(self):
        result = self.ctid_ng.delete_user_me_voicemail_message_result(1, '42')

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_get_voicemail_message(self):
        result = self.ctid_ng.get_voicemail_message_result(1, '42')

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_get_user_voicemail_message(self):
        result = self.ctid_ng.get_user_me_voicemail_message_result(1, '42')

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_put_voicemail_message(self):
        result = self.ctid_ng.put_voicemail_message_result({}, 1, '42')

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_put_user_voicemail_message(self):
        result = self.ctid_ng.put_user_me_voicemail_message_result({}, 1, '42')

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_get_voicemail_recording(self):
        result = self.ctid_ng.get_voicemail_recording_result(1, '42')

        assert_that(result.status_code, equal_to(401))

    def test_auth_on_get_user_voicemail_recording(self):
        result = self.ctid_ng.get_user_me_voicemail_recording_result(1, '42')

        assert_that(result.status_code, equal_to(401))
