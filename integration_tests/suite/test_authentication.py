# Copyright 2015-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import (
    assert_that,
    calling,
    contains_string,
    has_properties,
)

from wazo_test_helpers.hamcrest.raises import raises
from wazo_calld_client.exceptions import CalldError

from .helpers.base import IntegrationTest
from .helpers.constants import INVALID_ACL_TOKEN, VALID_TOKEN
from .helpers.wait_strategy import CalldUpWaitStrategy


class TestAuthentication(IntegrationTest):
    asset = 'basic_rest'

    def test_no_auth_gives_401(self):
        self.calld_client.set_token(None)
        assert_that(
            calling(self.calld_client.calls.get_call).with_args('my-call'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_invalid_auth_gives_401(self):
        self.calld_client.set_token('invalid-token')
        assert_that(
            calling(self.calld_client.calls.get_call).with_args('my-call'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_invalid_acl_gives_401(self):
        self.calld_client.set_token(INVALID_ACL_TOKEN)
        assert_that(
            calling(self.calld_client.calls.get_call).with_args('my-call'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_valid_auth_gives_result(self):
        self.calld_client.set_token(VALID_TOKEN)
        assert_that(
            calling(self.calld_client.calls.get_call).with_args('my-call'),
            raises(CalldError).matching(has_properties(status_code=404)),
        )


class TestAuthenticationError(IntegrationTest):
    asset = 'no_auth_server'
    wait_strategy = CalldUpWaitStrategy()

    def test_no_auth_server_gives_503(self):
        assert_that(
            calling(self.calld_client.calls.get_call).with_args('my-call'),
            raises(CalldError).matching(
                has_properties(
                    status_code=503,
                    message=contains_string('Authentication server'),
                )
            ),
        )


class TestAuthenticationCoverage(IntegrationTest):
    asset = 'basic_rest'

    def setUp(self):
        super().setUp()
        self.calld_client.set_token(None)

    def test_auth_on_line_endpoint_list(self):
        assert_that(
            calling(self.calld_client.lines.list_lines),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_trunk_endpoint_list(self):
        assert_that(
            calling(self.calld_client.trunks.list_trunks),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_list_calls(self):
        assert_that(
            calling(self.calld_client.calls.list_calls),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_list_user_calls(self):
        assert_that(
            calling(self.calld_client.calls.list_calls_from_user),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_get_call(self):
        assert_that(
            calling(self.calld_client.calls.get_call).with_args('id'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_new_call(self):
        assert_that(
            calling(self.calld_client.calls.make_call).with_args(call={}),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_new_user_call(self):
        assert_that(
            calling(self.calld_client.calls.make_call_from_user).with_args('extension'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_hangup(self):
        assert_that(
            calling(self.calld_client.calls.hangup).with_args('id'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_user_hangup(self):
        assert_that(
            calling(self.calld_client.calls.hangup_from_user).with_args('id'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_list_user_transfer(self):
        assert_that(
            calling(self.calld_client.transfers.list_transfers_from_user),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_get_transfer(self):
        assert_that(
            calling(self.calld_client.transfers.get_transfer).with_args('id'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_new_transfer(self):
        assert_that(
            calling(self.calld_client.transfers.make_transfer).with_args(
                'transferred', 'initiatior', 'context', 'exten'
            ),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_new_user_transfer(self):
        assert_that(
            calling(self.calld_client.transfers.make_transfer_from_user).with_args(
                'exten', 'initiatior', 'flow'
            ),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_transfer_cancel(self):
        assert_that(
            calling(self.calld_client.transfers.cancel_transfer).with_args('id'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_cancel_user_transfer(self):
        assert_that(
            calling(self.calld_client.transfers.cancel_transfer_from_user).with_args(
                'id'
            ),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_transfer_complete(self):
        assert_that(
            calling(self.calld_client.transfers.complete_transfer).with_args('id'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_complete_user_transfer(self):
        assert_that(
            calling(self.calld_client.transfers.complete_transfer_from_user).with_args(
                'id'
            ),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_get_voicemail(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail).with_args('id'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_get_user_voicemail(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_from_user),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_get_voicemail_folder(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_folder).with_args(
                'voicemail_id', 'folder_id'
            ),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_get_user_voicemail_folder(self):
        assert_that(
            calling(
                self.calld_client.voicemails.get_voicemail_folder_from_user
            ).with_args('folder_id'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_delete_voicemail_message(self):
        assert_that(
            calling(self.calld_client.voicemails.delete_voicemail_message).with_args(
                'voicemail_id', 'message_id'
            ),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_delete_user_voicemail_message(self):
        assert_that(
            calling(
                self.calld_client.voicemails.delete_voicemail_message_from_user
            ).with_args('message_id'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_get_voicemail_message(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_message).with_args(
                'voicemail_id', 'message_id'
            ),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_get_user_voicemail_message(self):
        assert_that(
            calling(
                self.calld_client.voicemails.get_voicemail_message_from_user
            ).with_args('message_id'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_put_voicemail_message(self):
        assert_that(
            calling(self.calld_client.voicemails.move_voicemail_message).with_args(
                'voicemail_id', 'message_id', 'dest_folder_id'
            ),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_put_user_voicemail_message(self):
        assert_that(
            calling(
                self.calld_client.voicemails.move_voicemail_message_from_user
            ).with_args('message_id', 'dest_folder_id'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_get_voicemail_recording(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_recording).with_args(
                'voicemail_id', 'message_id'
            ),
            raises(CalldError).matching(has_properties(status_code=401)),
        )

    def test_auth_on_get_user_voicemail_recording(self):
        assert_that(
            calling(
                self.calld_client.voicemails.get_voicemail_recording_from_user
            ).with_args('message_id'),
            raises(CalldError).matching(has_properties(status_code=401)),
        )
