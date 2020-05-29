# Copyright 2019-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import uuid

from hamcrest import (
    assert_that,
    calling,
    contains,
    contains_string,
    equal_to,
    has_entries,
    has_entry,
    has_properties,
    not_,
)

from xivo_test_helpers.hamcrest.raises import raises
from wazo_calld_client.exceptions import CalldError

from .helpers.auth import MockUserToken
from .helpers.base import RealAsteriskIntegrationTest
from .helpers.confd import (
    MockUser,
    MockVoicemail,
)
from .helpers.constants import ASSET_ROOT, VALID_TENANT
from .helpers.hamcrest_ import HamcrestARIChannel


VALID_GREETINGS = ('busy', 'unavailable', 'name')
wave_file = os.path.join(ASSET_ROOT, 'voicemail_greetings', 'bunny_29.wav')
with open(wave_file, 'rb') as f:
    WAVE_DATA_1 = f.read()

wave_file = os.path.join(ASSET_ROOT, 'voicemail_greetings', 'bunny_07.wav')
with open(wave_file, 'rb') as f:
    WAVE_DATA_2 = f.read()


class TestVoicemails(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def setUp(self):
        super().setUp()
        self.c = HamcrestARIChannel(self.ari)
        self.confd.reset()

        self._voicemail_id = 1234
        self._user_token = str(uuid.uuid4())
        self._user_uuid = str(uuid.uuid4())

        self.confd.set_users(MockUser(uuid=self._user_uuid,
                                      voicemail={'id': self._voicemail_id}))
        self.confd.set_voicemails(
            MockVoicemail(self._voicemail_id, "8000", "voicemail-name",
                          "default", user_uuids=[self._user_uuid])
        )
        self.auth.set_token(MockUserToken(self._user_token, user_uuid=self._user_uuid,
                                          tenant_uuid=VALID_TENANT))
        self.calld_client.set_token(self._user_token)

    def test_voicemail_head_greeting_invalid_voicemail(self):
        exists = self.calld_client.voicemails.voicemail_greeting_exists(
            "not-exists", "busy"
        )
        assert_that(not_(exists))

    def test_voicemail_head_greeting_invalid_greeting(self):
        exists = self.calld_client.voicemails.voicemail_greeting_exists(
            self._voicemail_id, "not-exists"
        )
        assert_that(not_(exists))

    def test_voicemail_get_greeting_invalid_voicemail(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_greeting).with_args(
                "not-exists", "busy"
            ),
            raises(CalldError).matching(has_properties(
                # FIXME(sileht): All voicemail endpoints return 400 instead of
                # 404 here
                status_code=400,
                message=contains_string("Invalid voicemail ID")
            ))
        )

    def test_voicemail_get_greeting_invalid_greeting(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_greeting).with_args(
                self._voicemail_id, "not-exists"
            ),
            raises(CalldError).matching(has_properties(
                status_code=404,
                message=contains_string("No such voicemail greeting"),
                details=has_entry("greeting", "not-exists"),
            ))
        )

    def test_voicemail_copy_greeting_invalid_dest_greeting(self):
        assert_that(
            calling(self.calld_client.voicemails.copy_voicemail_greeting).with_args(
                self._voicemail_id, "busy", "not-exists"
            ),
            raises(CalldError).matching(has_properties(
                status_code=400,
                message=contains_string("Sent data is invalid"),
                details=has_entry("dest_greeting", contains(
                    has_entries(
                        constraint=has_entry("choices", equal_to(
                            ["unavailable", "busy", "name"]
                        )),
                        message="Not a valid choice."


                    )
                ))
            ))
        )

    def test_voicemail_get_greeting_invalid_greeting_from_user(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_greeting_from_user).with_args(
                "not-exists"
            ),
            raises(CalldError).matching(has_properties(
                status_code=404,
                message=contains_string("No such voicemail greeting"),
                details=has_entry("greeting", "not-exists"),
            ))
        )

    def test_voicemail_put_unset_greeting(self):
        assert_that(
            calling(self.calld_client.voicemails.update_voicemail_greeting).with_args(
                self._voicemail_id, "busy", WAVE_DATA_1
            ),
            raises(CalldError).matching(has_properties(
                status_code=404,
                message=contains_string("No such voicemail greeting"),
                details=has_entry("greeting", "busy"),
            ))
        )

    def test_voicemail_put_unset_greeting_from_user(self):
        assert_that(
            calling(self.calld_client.voicemails.update_voicemail_greeting_from_user).with_args(
                "busy", WAVE_DATA_1
            ),
            raises(CalldError).matching(has_properties(
                status_code=404,
                message=contains_string("No such voicemail greeting"),
                details=has_entry("greeting", "busy"),
            ))
        )

    def test_voicemail_head_unset_greeting(self):
        exists = self.calld_client.voicemails.voicemail_greeting_exists(
            self._voicemail_id, "busy"
        )
        assert_that(not_(exists))

    def test_voicemail_get_unset_greeting(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_greeting).with_args(
                self._voicemail_id, "busy"
            ),
            raises(CalldError).matching(has_properties(
                status_code=404,
                message=contains_string("No such voicemail greeting"),
                details=has_entry("greeting", "busy"),
            ))
        )

    def test_voicemail_get_unset_greeting_from_user(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_greeting_from_user).with_args(
                "busy"
            ),
            raises(CalldError).matching(has_properties(
                status_code=404,
                message=contains_string("No such voicemail greeting"),
                details=has_entry("greeting", "busy"),
            ))
        )

    def test_voicemail_delete_unset_greeting(self):
        self.calld_client.voicemails.delete_voicemail_greeting(
            self._voicemail_id, "busy"
        )

    def test_voicemail_delete_unset_greeting_from_user(self):
        self.calld_client.voicemails.delete_voicemail_greeting_from_user(
            "busy"
        )

    def test_voicemail_create_invalid_body(self):
        assert_that(
            calling(self.calld_client.voicemails.create_voicemail_greeting).with_args(
                self._voicemail_id, "busy", ""
            ),
            raises(CalldError).matching(has_properties(
                status_code=400,
                message=contains_string("Invalid voicemail greeting"),
                details=has_entry("greeting", "busy"),
            ))
        )

    def test_voicemail_create_invalid_body_from_user(self):
        assert_that(
            calling(self.calld_client.voicemails.create_voicemail_greeting_from_user).with_args(
                "busy", ""
            ),
            raises(CalldError).matching(has_properties(
                status_code=400,
                message=contains_string("Invalid voicemail greeting"),
                details=has_entry("greeting", "busy"),
            ))
        )

    def test_voicemail_put_invalid_body(self):
        self.calld_client.voicemails.create_voicemail_greeting(
            self._voicemail_id, "busy", WAVE_DATA_1
        )
        assert_that(
            calling(self.calld_client.voicemails.update_voicemail_greeting).with_args(
                self._voicemail_id, "busy", ""
            ),
            raises(CalldError).matching(has_properties(
                status_code=400,
                message=contains_string("Invalid voicemail greeting"),
                details=has_entry("greeting", "busy"),
            ))
        )

        self.calld_client.voicemails.delete_voicemail_greeting(
            self._voicemail_id, "busy"
        )

    def test_voicemail_put_invalid_body_from_user(self):
        self.calld_client.voicemails.create_voicemail_greeting_from_user(
            "busy", WAVE_DATA_1
        )
        assert_that(
            calling(self.calld_client.voicemails.update_voicemail_greeting_from_user).with_args(
                "busy", ""
            ),
            raises(CalldError).matching(has_properties(
                status_code=400,
                message=contains_string("Invalid voicemail greeting"),
                details=has_entry("greeting", "busy"),
            ))
        )

        self.calld_client.voicemails.delete_voicemail_greeting_from_user(
            "busy"
        )

    def test_voicemail_user_has_no_voicemail(self):
        self.confd.set_users(MockUser(uuid=self._user_uuid, voicemail=None))
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_from_user),
            raises(CalldError).matching(has_properties(
                status_code=404,
                message=contains_string("No such user voicemail"),
                details=has_entry("user_uuid", self._user_uuid),
            ))
        )

    def test_voicemail_workflow(self):
        self.calld_client.voicemails.create_voicemail_greeting(
            self._voicemail_id, "busy", WAVE_DATA_1
        )
        self.calld_client.voicemails.copy_voicemail_greeting(
            self._voicemail_id, "busy", "unavailable"
        )
        self.calld_client.voicemails.copy_voicemail_greeting(
            self._voicemail_id, "busy", "name"
        )

        assert_that(
            calling(self.calld_client.voicemails.create_voicemail_greeting).with_args(
                self._voicemail_id, "busy", WAVE_DATA_2
            ),
            raises(CalldError).matching(has_properties(
                status_code=409,
                message=contains_string("Voicemail greeting already exists"),
                details=has_entry("greeting", "busy"),
            ))
        )

        for greeting in VALID_GREETINGS:
            exists = self.calld_client.voicemails.voicemail_greeting_exists(
                self._voicemail_id, greeting
            )
            assert_that(exists)

            data = self.calld_client.voicemails.get_voicemail_greeting(
                self._voicemail_id, greeting
            )
            assert_that(data, equal_to(WAVE_DATA_1))

        self.calld_client.voicemails.update_voicemail_greeting(
            self._voicemail_id, "busy", WAVE_DATA_2
        )
        data = self.calld_client.voicemails.get_voicemail_greeting(
            self._voicemail_id, "busy"
        )
        assert_that(data, equal_to(WAVE_DATA_2))

        for greeting in VALID_GREETINGS:
            self.calld_client.voicemails.delete_voicemail_greeting(
                self._voicemail_id, greeting
            )

        for greeting in VALID_GREETINGS:
            assert_that(
                calling(self.calld_client.voicemails.get_voicemail_greeting).with_args(
                    self._voicemail_id, greeting
                ),
                raises(CalldError).matching(has_properties(
                    status_code=404,
                    message=contains_string("No such voicemail greeting"),
                    details=has_entry("greeting", greeting),
                ))
            )

    def test_voicemail_workflow_from_user(self):
        self.calld_client.voicemails.create_voicemail_greeting_from_user(
            "busy", WAVE_DATA_1
        )
        self.calld_client.voicemails.copy_voicemail_greeting_from_user(
            "busy", "unavailable"
        )
        self.calld_client.voicemails.copy_voicemail_greeting_from_user(
            "busy", "name"
        )

        assert_that(
            calling(self.calld_client.voicemails.create_voicemail_greeting_from_user).with_args(
                "busy", WAVE_DATA_2
            ),
            raises(CalldError).matching(has_properties(
                status_code=409,
                message=contains_string("Voicemail greeting already exists"),
                details=has_entry("greeting", "busy"),
            ))
        )

        for greeting in VALID_GREETINGS:
            data = self.calld_client.voicemails.get_voicemail_greeting_from_user(
                greeting
            )
            assert_that(data, equal_to(WAVE_DATA_1))

        self.calld_client.voicemails.update_voicemail_greeting_from_user(
            "busy", WAVE_DATA_2
        )
        data = self.calld_client.voicemails.get_voicemail_greeting_from_user(
            "busy"
        )
        assert_that(data, equal_to(WAVE_DATA_2))

        for greeting in VALID_GREETINGS:
            self.calld_client.voicemails.delete_voicemail_greeting_from_user(
                greeting
            )

        for greeting in VALID_GREETINGS:
            assert_that(
                calling(self.calld_client.voicemails.get_voicemail_greeting_from_user).with_args(
                    greeting
                ),
                raises(CalldError).matching(has_properties(
                    status_code=404,
                    message=contains_string("No such voicemail greeting"),
                    details=has_entry("greeting", greeting),
                ))
            )
