# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import uuid

from hamcrest import (
    assert_that,
    calling,
    contains_string,
    equal_to,
    has_property,
    has_properties,
)

import requests

from xivo_test_helpers.hamcrest.raises import raises

from .helpers.auth import MockUserToken
from .helpers.base import RealAsteriskIntegrationTest
from .helpers.confd import (
    MockUser,
    MockVoicemail,
)
from .helpers.constants import ASSET_ROOT, VALID_TENANT
from .helpers.hamcrest_ import HamcrestARIChannel

VALID_GREETINGS = ('busy', 'unavailable', 'name')
WAVE_FILE = os.path.join(ASSET_ROOT, 'bugs_29.wav')
with open(WAVE_FILE, 'rb') as f:
    WAVE_DATA = f.read()


class TestVoicemails(RealAsteriskIntegrationTest):

    asset = 'real_asterisk'

    def setUp(self):
        super().setUp()
        self.c = HamcrestARIChannel(self.ari)
        self.confd.reset()

        self._voicemail_id = 1234
        self._user_token = str(uuid.uuid4())
        self._user_uuid = str(uuid.uuid4())

        self.confd.set_users(MockUser(uuid=self._user_uuid))
        self.confd.set_voicemails(
            MockVoicemail(self._voicemail_id, "8000", "voicemail-name",
                          "default", user_uuids=[self._user_uuid])
        )
        self.auth.set_token(MockUserToken(self._user_token, user_uuid=self._user_uuid,
                                          tenant_uuid=VALID_TENANT))
        self.calld_client.set_token(self._user_token)

    def test_voicemail_get_greeting_invalid_voicemail(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_greeting).with_args(
                "not-exists", "busy"
            ),
            raises(requests.HTTPError).matching(has_property(
                'response', has_properties(
                    status_code=404,
                    text=contains_string("Invalid voicemail ID")
                )
            ))
        )

    def test_voicemail_get_greeting_invalid_greeting(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_greeting).with_args(
                self._voicemail_id, "not-exists"
            ),
            raises(requests.HTTPError).matching(has_property(
                'response', has_properties(
                    status_code=404,
                    text=contains_string("Invalid voicemail greeting")
                )
            ))
        )

    def test_voicemail_copy_greeting_invalid_dest_greeting(self):
        assert_that(
            calling(self.calld_client.voicemails.copy_voicemail_greeting).with_args(
                self._voicemail_id, "busy", "not-exists"
            ),
            raises(requests.HTTPError).matching(has_property(
                'response', has_properties(
                    status_code=400,
                    text=contains_string("Not a valid choice")
                )
            ))
        )

    def test_voicemail_get_greeting_invalid_greeting_from_user(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_greeting_from_user).with_args(
                "not-exists"
            ),
            raises(requests.HTTPError).matching(has_property(
                'response', has_properties(
                    status_code=404,
                    text=contains_string("Invalid voicemail greeting")
                )
            ))
        )

    def test_voicemail_get_unset_greeting(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_greeting).with_args(
                self._voicemail_id, "busy"
            ),
            raises(requests.HTTPError).matching(has_property(
                'response', has_properties(
                    status_code=404,
                    text=contains_string("No such voicemail greeting")
                )
            ))
        )

    def test_voicemail_get_unset_greeting_from_user(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_greeting_from_user).with_args(
                "busy"
            ),
            raises(requests.HTTPError).matching(has_property(
                'response', has_properties(
                    status_code=404,
                    text=contains_string("No such voicemail greeting")
                )
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

    def test_voicemail_workflow(self):
        self.calld_client.voicemails.update_voicemail_greeting(
            self._voicemail_id, "busy", WAVE_DATA
        )
        self.calld_client.voicemails.copy_voicemail_greeting(
            self._voicemail_id, "busy", "unavailable"
        )
        self.calld_client.voicemails.copy_voicemail_greeting(
            self._voicemail_id, "busy", "name"
        )

        for greeting in VALID_GREETINGS:
            data = self.calld_client.voicemails.get_voicemail_greeting(
                self._voicemail_id, greeting
            )
            assert_that(data, equal_to(WAVE_DATA))

        for greeting in VALID_GREETINGS:
            self.calld_client.voicemails.delete_voicemail_greeting(
                self._voicemail_id, greeting
            )

        for greeting in VALID_GREETINGS:
            assert_that(
                calling(self.calld_client.voicemails.get_voicemail_greeting).with_args(
                    self._voicemail_id, greeting
                ),
                raises(requests.HTTPError).matching(has_property(
                    'response', has_properties(
                        status_code=404,
                        text=contains_string("No such voicemail greeting")
                    )
                ))
            )

    def test_voicemail_workflow_from_user(self):
        self.calld_client.voicemails.update_voicemail_greeting_from_user(
            "busy", WAVE_DATA
        )
        self.calld_client.voicemails.copy_voicemail_greeting_from_user(
            "busy", "unavailable"
        )
        self.calld_client.voicemails.copy_voicemail_greeting_from_user(
            "busy", "name"
        )

        for greeting in VALID_GREETINGS:
            data = self.calld_client.voicemails.get_voicemail_greeting_from_user(
                greeting
            )
            assert_that(data, equal_to(WAVE_DATA))

        for greeting in VALID_GREETINGS:
            self.calld_client.voicemails.delete_voicemail_greeting_from_user(
                greeting
            )

        for greeting in VALID_GREETINGS:
            assert_that(
                calling(self.calld_client.voicemails.get_voicemail_greeting_from_user).with_args(
                    greeting
                ),
                raises(requests.HTTPError).matching(has_property(
                    'response', has_properties(
                        status_code=404,
                        text=contains_string("No such voicemail greeting")
                    )
                ))
            )
