# Copyright 2019-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import uuid

from hamcrest import (
    assert_that,
    calling,
    contains_exactly,
    contains_string,
    equal_to,
    has_entries,
    has_entry,
    has_properties,
    is_,
)
from wazo_calld_client.exceptions import CalldError
from wazo_test_helpers.hamcrest.raises import raises

from .helpers.confd import MockVoicemail
from .helpers.constants import (
    ASSET_ROOT,
    VALID_TENANT,
    VALID_TENANT_MULTITENANT_1,
    VALID_TENANT_MULTITENANT_2,
)
from .helpers.hamcrest_ import HamcrestARIChannel
from .helpers.real_asterisk import RealAsteriskIntegrationTest

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
        self._user_uuid = str(uuid.uuid4())

        voicemail = MockVoicemail(
            self._voicemail_id,
            '8000',
            'voicemail-name',
            'default',
            user_uuids=[self._user_uuid],
            tenant_uuid=VALID_TENANT,
        )
        self.confd.set_user_voicemails({self._user_uuid: [voicemail]})
        self.confd.set_voicemails(voicemail)
        self.calld_client = self.make_user_calld(
            self._user_uuid, tenant_uuid=VALID_TENANT
        )

    def test_voicemail_get_invalid(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail).with_args('not-found'),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    message=contains_string('Invalid voicemail ID'),
                    details=has_entry('voicemail_id', 'not-found'),
                )
            ),
        )

    def test_voicemail_get_not_found(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail).with_args(123),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail'),
                    details=has_entry('voicemail_id', 123),
                )
            ),
        )

    def test_voicemail_get_tenant_isolation(self):
        user_uuid_1 = str(uuid.uuid4())
        user_uuid_2 = str(uuid.uuid4())
        voicemail_id_1 = 111
        voicemail_id_2 = 22
        voicemail_1 = MockVoicemail(
            voicemail_id_1,
            '8000',
            'voicemail-name',
            'multitenant-1',
            tenant_uuid=VALID_TENANT_MULTITENANT_1,
        )
        voicemail_2 = MockVoicemail(
            voicemail_id_2,
            '8000',
            'voicemail-name',
            'multitenant-2',
            tenant_uuid=VALID_TENANT_MULTITENANT_2,
        )
        self.confd.set_voicemails(voicemail_1, voicemail_2)
        calld_1 = self.make_user_calld(
            user_uuid_1, tenant_uuid=VALID_TENANT_MULTITENANT_1
        )
        calld_2 = self.make_user_calld(
            user_uuid_2, tenant_uuid=VALID_TENANT_MULTITENANT_2
        )

        # tenant 1, voicemail 1 = OK
        voicemail = calld_1.voicemails.get_voicemail(voicemail_id_1)
        assert voicemail['id'] == voicemail_id_1

        # tenant 1, voicemail 2 = NOK
        assert_that(
            calling(calld_1.voicemails.get_voicemail).with_args(voicemail_id_2),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail'),
                    details=has_entry('voicemail_id', voicemail_id_2),
                )
            ),
        )

        # tenant 2, voicemail 1 = NOK
        assert_that(
            calling(calld_2.voicemails.get_voicemail).with_args(voicemail_id_1),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail'),
                    details=has_entry('voicemail_id', voicemail_id_1),
                )
            ),
        )

        # tenant 2, voicemail 2 = OK
        voicemail = calld_2.voicemails.get_voicemail(voicemail_id_2)
        assert voicemail['id'] == voicemail_id_2

    def test_voicemail_get(self):
        voicemail = self.calld_client.voicemails.get_voicemail(self._voicemail_id)
        assert voicemail['id'] == self._voicemail_id
        assert voicemail['name'] == 'voicemail-name'

    def test_voicemail_get_from_user_no_voicemail(self):
        self.confd.set_user_voicemails({self._user_uuid: []})
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_from_user),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such user voicemail'),
                    details=has_entry('user_uuid', self._user_uuid),
                )
            ),
        )

    def test_voicemail_head_greeting_invalid_voicemail(self):
        exists = self.calld_client.voicemails.voicemail_greeting_exists(
            'not-exists', 'busy'
        )
        assert_that(exists, is_(False))

    def test_voicemail_head_greeting_invalid_greeting(self):
        exists = self.calld_client.voicemails.voicemail_greeting_exists(
            self._voicemail_id, 'not-exists'
        )
        assert_that(exists, is_(False))

    def test_voicemail_get_greeting_invalid_voicemail(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_greeting).with_args(
                'not-exists', 'busy'
            ),
            raises(CalldError).matching(
                has_properties(
                    # FIXME(sileht): All voicemail endpoints return 400 instead of
                    # 404 here
                    status_code=400,
                    message=contains_string('Invalid voicemail ID'),
                )
            ),
        )

    def test_voicemail_get_greeting_invalid_greeting(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_greeting).with_args(
                self._voicemail_id, 'not-exists'
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail greeting'),
                    details=has_entry('greeting', 'not-exists'),
                )
            ),
        )

    def test_voicemail_get_greeting_unset(self):
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_greeting).with_args(
                self._voicemail_id, 'busy'
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail greeting'),
                    details=has_entry('greeting', 'busy'),
                )
            ),
        )

    def test_voicemail_copy_greeting_invalid_dest_greeting(self):
        assert_that(
            calling(self.calld_client.voicemails.copy_voicemail_greeting).with_args(
                self._voicemail_id, 'busy', 'not-exists'
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    message=contains_string('Sent data is invalid'),
                    details=has_entry(
                        'dest_greeting',
                        contains_exactly(
                            has_entries(
                                constraint=has_entry(
                                    'choices', equal_to(['unavailable', 'busy', 'name'])
                                ),
                                message='Must be one of: unavailable, busy, name.',
                            )
                        ),
                    ),
                )
            ),
        )

    def test_voicemail_head_greeting_from_user_invalid_greeting(self):
        exists = self.calld_client.voicemails.voicemail_greeting_from_user_exists(
            'not-exists'
        )
        assert_that(exists, is_(False))

    def test_voicemail_head_greeting_from_user_unset_greeting(self):
        exists = self.calld_client.voicemails.voicemail_greeting_from_user_exists(
            'busy'
        )
        assert_that(exists, is_(False))

    def test_voicemail_get_greeting_from_user_invalid_greeting(self):
        assert_that(
            calling(
                self.calld_client.voicemails.get_voicemail_greeting_from_user
            ).with_args('not-exists'),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail greeting'),
                    details=has_entry('greeting', 'not-exists'),
                )
            ),
        )

    def test_voicemail_get_greeting_from_user_unset_greeting(self):
        assert_that(
            calling(
                self.calld_client.voicemails.get_voicemail_greeting_from_user
            ).with_args('busy'),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail greeting'),
                    details=has_entry('greeting', 'busy'),
                )
            ),
        )

    def test_voicemail_put_greeting_unset(self):
        assert_that(
            calling(self.calld_client.voicemails.update_voicemail_greeting).with_args(
                self._voicemail_id, 'busy', WAVE_DATA_1
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail greeting'),
                    details=has_entry('greeting', 'busy'),
                )
            ),
        )

    def test_voicemail_put_greeting_invalid_body(self):
        self.calld_client.voicemails.create_voicemail_greeting(
            self._voicemail_id, 'busy', WAVE_DATA_1
        )
        assert_that(
            calling(self.calld_client.voicemails.update_voicemail_greeting).with_args(
                self._voicemail_id, 'busy', ''
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    message=contains_string('Invalid voicemail greeting'),
                    details=has_entry('greeting', 'busy'),
                )
            ),
        )

        self.calld_client.voicemails.delete_voicemail_greeting(
            self._voicemail_id, 'busy'
        )

    def test_voicemail_put_greeting_from_user_unset(self):
        assert_that(
            calling(
                self.calld_client.voicemails.update_voicemail_greeting_from_user
            ).with_args('busy', WAVE_DATA_1),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail greeting'),
                    details=has_entry('greeting', 'busy'),
                )
            ),
        )

    def test_voicemail_put_greeting_from_user_invalid_body(self):
        self.calld_client.voicemails.create_voicemail_greeting_from_user(
            'busy', WAVE_DATA_1
        )
        assert_that(
            calling(
                self.calld_client.voicemails.update_voicemail_greeting_from_user
            ).with_args('busy', ''),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    message=contains_string('Invalid voicemail greeting'),
                    details=has_entry('greeting', 'busy'),
                )
            ),
        )

        self.calld_client.voicemails.delete_voicemail_greeting_from_user('busy')

    def test_voicemail_delete_unset_greeting(self):
        self.calld_client.voicemails.delete_voicemail_greeting(
            self._voicemail_id, 'busy'
        )

    def test_voicemail_delete_unset_greeting_from_user(self):
        self.calld_client.voicemails.delete_voicemail_greeting_from_user('busy')

    def test_voicemail_create_invalid_body(self):
        assert_that(
            calling(self.calld_client.voicemails.create_voicemail_greeting).with_args(
                self._voicemail_id, 'busy', ''
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    message=contains_string('Invalid voicemail greeting'),
                    details=has_entry('greeting', 'busy'),
                )
            ),
        )

    def test_voicemail_create_invalid_body_from_user(self):
        assert_that(
            calling(
                self.calld_client.voicemails.create_voicemail_greeting_from_user
            ).with_args('busy', ''),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    message=contains_string('Invalid voicemail greeting'),
                    details=has_entry('greeting', 'busy'),
                )
            ),
        )

    def test_voicemail_greeting_workflow(self):
        self.calld_client.voicemails.create_voicemail_greeting(
            self._voicemail_id, 'busy', WAVE_DATA_1
        )
        self.calld_client.voicemails.copy_voicemail_greeting(
            self._voicemail_id, 'busy', 'unavailable'
        )
        self.calld_client.voicemails.copy_voicemail_greeting(
            self._voicemail_id, 'busy', 'name'
        )

        assert_that(
            calling(self.calld_client.voicemails.create_voicemail_greeting).with_args(
                self._voicemail_id, 'busy', WAVE_DATA_2
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=409,
                    message=contains_string('Voicemail greeting already exists'),
                    details=has_entry('greeting', 'busy'),
                )
            ),
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
            self._voicemail_id, 'busy', WAVE_DATA_2
        )
        data = self.calld_client.voicemails.get_voicemail_greeting(
            self._voicemail_id, 'busy'
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
                raises(CalldError).matching(
                    has_properties(
                        status_code=404,
                        message=contains_string('No such voicemail greeting'),
                        details=has_entry('greeting', greeting),
                    )
                ),
            )

    def test_voicemail_greeting_workflow_from_user(self):
        self.calld_client.voicemails.create_voicemail_greeting_from_user(
            'busy', WAVE_DATA_1
        )
        self.calld_client.voicemails.copy_voicemail_greeting_from_user(
            'busy', 'unavailable'
        )
        self.calld_client.voicemails.copy_voicemail_greeting_from_user('busy', 'name')

        assert_that(
            calling(
                self.calld_client.voicemails.create_voicemail_greeting_from_user
            ).with_args('busy', WAVE_DATA_2),
            raises(CalldError).matching(
                has_properties(
                    status_code=409,
                    message=contains_string('Voicemail greeting already exists'),
                    details=has_entry('greeting', 'busy'),
                )
            ),
        )

        for greeting in VALID_GREETINGS:
            exists = self.calld_client.voicemails.voicemail_greeting_from_user_exists(
                greeting
            )
            assert_that(exists)

            data = self.calld_client.voicemails.get_voicemail_greeting_from_user(
                greeting
            )
            assert_that(data, equal_to(WAVE_DATA_1))

        self.calld_client.voicemails.update_voicemail_greeting_from_user(
            'busy', WAVE_DATA_2
        )
        data = self.calld_client.voicemails.get_voicemail_greeting_from_user('busy')
        assert_that(data, equal_to(WAVE_DATA_2))

        for greeting in VALID_GREETINGS:
            self.calld_client.voicemails.delete_voicemail_greeting_from_user(greeting)

        for greeting in VALID_GREETINGS:
            assert_that(
                calling(
                    self.calld_client.voicemails.get_voicemail_greeting_from_user
                ).with_args(greeting),
                raises(CalldError).matching(
                    has_properties(
                        status_code=404,
                        message=contains_string('No such voicemail greeting'),
                        details=has_entry('greeting', greeting),
                    )
                ),
            )
