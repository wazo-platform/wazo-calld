# Copyright 2019-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import uuid
from contextlib import contextmanager

import pytest
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
from wazo_test_helpers import until
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

        self._folder_id = 1  # INBOX folder. Present in Docker image
        self._folder_old_id = 2  # Old folder. Present in Docker image
        self._message_id = '1724107750-00000001'  # Present in Docker image

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

    def test_voicemail_get_folder_invalid(self):
        # invalid voicemail
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_folder).with_args(
                'invalid', 123
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    message=contains_string('Invalid voicemail ID'),
                    details=has_entry('voicemail_id', 'invalid'),
                )
            ),
        )

        # invalid folder
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_folder).with_args(
                123, 'invalid'
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    message=contains_string('Invalid voicemail folder ID'),
                    details=has_entry('folder_id', 'invalid'),
                )
            ),
        )

    def test_voicemail_get_folder_not_found(self):
        # voicemail not found
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_folder).with_args(
                123, 123
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail'),
                    details=has_entry('voicemail_id', 123),
                )
            ),
        )

        # folder not found
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_folder).with_args(
                self._voicemail_id, 123
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail folder'),
                    details=has_entry('folder_id', 123),
                )
            ),
        )

    def test_voicemail_get_folder_tenant_isolation(self):
        user_uuid_1 = str(uuid.uuid4())
        user_uuid_2 = str(uuid.uuid4())
        voicemail_id_1 = 111
        voicemail_id_2 = 222
        folder_id = 1
        voicemail_1 = MockVoicemail(
            voicemail_id_1,
            '8001',
            'voicemail-name',
            'multitenant-1',
            tenant_uuid=VALID_TENANT_MULTITENANT_1,
        )
        voicemail_2 = MockVoicemail(
            voicemail_id_2,
            '8002',
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
        folder = calld_1.voicemails.get_voicemail_folder(voicemail_id_1, folder_id)
        assert folder['id'] == folder_id

        # tenant 1, voicemail 2 = NOK
        assert_that(
            calling(calld_1.voicemails.get_voicemail_folder).with_args(
                voicemail_id_2, folder_id
            ),
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
            calling(calld_2.voicemails.get_voicemail_folder).with_args(
                voicemail_id_1, folder_id
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail'),
                    details=has_entry('voicemail_id', voicemail_id_1),
                )
            ),
        )

        # tenant 2, voicemail 2 = OK
        folder = calld_2.voicemails.get_voicemail_folder(voicemail_id_2, folder_id)
        assert folder['id'] == folder_id

    def test_voicemail_get_folder(self):
        folder = self.calld_client.voicemails.get_voicemail_folder(
            self._voicemail_id, self._folder_id
        )
        assert folder['id'] == self._folder_id
        assert folder['name'] == 'inbox'
        assert folder['messages'][0]['id'] == self._message_id

    def test_voicemail_get_message_invalid(self):
        # invalid voicemail
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_message).with_args(
                'invalid', 123
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    message=contains_string('Invalid voicemail ID'),
                    details=has_entry('voicemail_id', 'invalid'),
                )
            ),
        )

        # invalid message
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_message).with_args(
                123, 'invalid!'
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    message=contains_string('Invalid voicemail message ID'),
                    details=has_entry('message_id', 'invalid!'),
                )
            ),
        )

    def test_voicemail_get_message_not_found(self):
        # voicemail not found
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_message).with_args(
                123, 123
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail'),
                    details=has_entry('voicemail_id', 123),
                )
            ),
        )

        # message not found
        assert_that(
            calling(self.calld_client.voicemails.get_voicemail_message).with_args(
                self._voicemail_id, 123
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail message'),
                    details=has_entry('message_id', '123'),
                )
            ),
        )

    def test_voicemail_get_message_tenant_isolation(self):
        user_uuid_1 = str(uuid.uuid4())
        user_uuid_2 = str(uuid.uuid4())
        voicemail_id_1 = 111
        voicemail_id_2 = 222
        message_id_1 = '1724107750-00000011'  # Present in Docker image
        message_id_2 = '1724107750-00000021'  # Present in Docker image
        voicemail_1 = MockVoicemail(
            voicemail_id_1,
            '8001',
            'voicemail-name',
            'multitenant-1',
            tenant_uuid=VALID_TENANT_MULTITENANT_1,
        )
        voicemail_2 = MockVoicemail(
            voicemail_id_2,
            '8002',
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
        message = calld_1.voicemails.get_voicemail_message(voicemail_id_1, message_id_1)
        assert message['id'] == message_id_1

        # tenant 1, voicemail 2 = NOK
        assert_that(
            calling(calld_1.voicemails.get_voicemail_message).with_args(
                voicemail_id_2, message_id_2
            ),
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
            calling(calld_2.voicemails.get_voicemail_message).with_args(
                voicemail_id_1, message_id_2
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail'),
                    details=has_entry('voicemail_id', voicemail_id_1),
                )
            ),
        )

        # tenant 2, voicemail 2 = OK
        message = calld_2.voicemails.get_voicemail_message(voicemail_id_2, message_id_2)
        assert message['id'] == message_id_2

    def test_voicemail_get_message(self):
        message = self.calld_client.voicemails.get_voicemail_message(
            self._voicemail_id, self._message_id
        )
        assert message['id'] == self._message_id
        assert message['caller_id_name'] == 'Alice'

    def test_voicemail_move_message_invalid(self):
        # invalid voicemail
        assert_that(
            calling(self.calld_client.voicemails.move_voicemail_message).with_args(
                'invalid', 123, self._folder_old_id
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    message=contains_string('Invalid voicemail ID'),
                    details=has_entry('voicemail_id', 'invalid'),
                )
            ),
        )

        # invalid message
        assert_that(
            calling(self.calld_client.voicemails.move_voicemail_message).with_args(
                123, 'invalid!', self._folder_old_id
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    message=contains_string('Invalid voicemail message ID'),
                    details=has_entry('message_id', 'invalid!'),
                )
            ),
        )

    def test_voicemail_move_message_not_found(self):
        # voicemail not found
        assert_that(
            calling(self.calld_client.voicemails.move_voicemail_message).with_args(
                123, 123, self._folder_old_id
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail'),
                    details=has_entry('voicemail_id', 123),
                )
            ),
        )

        # message not found
        assert_that(
            calling(self.calld_client.voicemails.move_voicemail_message).with_args(
                self._voicemail_id, 123, self._folder_old_id
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail message'),
                    details=has_entry('message_id', '123'),
                )
            ),
        )

    def test_voicemail_move_message_tenant_isolation(self):
        user_uuid_1 = str(uuid.uuid4())
        user_uuid_2 = str(uuid.uuid4())
        voicemail_id_1 = 111
        voicemail_id_2 = 222
        message_id_1 = '1724107750-00000011'  # Present in Docker image
        message_id_2 = '1724107750-00000021'  # Present in Docker image
        voicemail_1 = MockVoicemail(
            voicemail_id_1,
            '8001',
            'voicemail-name',
            'multitenant-1',
            tenant_uuid=VALID_TENANT_MULTITENANT_1,
        )
        voicemail_2 = MockVoicemail(
            voicemail_id_2,
            '8002',
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
        calld_1.voicemails.move_voicemail_message(
            voicemail_id_1, message_id_1, self._folder_old_id
        )
        message = calld_1.voicemails.get_voicemail_message(voicemail_id_1, message_id_1)
        assert message['folder']['id'] == self._folder_old_id

        # tenant 1, voicemail 2 = NOK
        assert_that(
            calling(calld_1.voicemails.move_voicemail_message).with_args(
                voicemail_id_2, message_id_2, self._folder_old_id
            ),
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
            calling(calld_2.voicemails.move_voicemail_message).with_args(
                voicemail_id_1, message_id_2, self._folder_old_id
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail'),
                    details=has_entry('voicemail_id', voicemail_id_1),
                )
            ),
        )

        # tenant 2, voicemail 2 = OK
        calld_2.voicemails.move_voicemail_message(
            voicemail_id_2, message_id_2, self._folder_old_id
        )
        message = calld_2.voicemails.get_voicemail_message(voicemail_id_2, message_id_2)
        assert message['folder']['id'] == self._folder_old_id

        # restore messages
        calld_1.voicemails.move_voicemail_message(
            voicemail_id_1, message_id_1, self._folder_id
        )
        calld_2.voicemails.move_voicemail_message(
            voicemail_id_2, message_id_2, self._folder_id
        )

    def test_voicemail_move_message(self):
        self.calld_client.voicemails.move_voicemail_message(
            self._voicemail_id, self._message_id, self._folder_old_id
        )
        message = self.calld_client.voicemails.get_voicemail_message(
            self._voicemail_id, self._message_id
        )
        assert message['id'] == self._message_id
        assert message['folder']['id'] == self._folder_old_id

        # restore file
        self.calld_client.voicemails.move_voicemail_message(
            self._voicemail_id, self._message_id, self._folder_id
        )

    def test_voicemail_delete_message_invalid(self):
        # invalid voicemail
        assert_that(
            calling(self.calld_client.voicemails.delete_voicemail_message).with_args(
                'invalid', 123
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    message=contains_string('Invalid voicemail ID'),
                    details=has_entry('voicemail_id', 'invalid'),
                )
            ),
        )

        # invalid message
        assert_that(
            calling(self.calld_client.voicemails.delete_voicemail_message).with_args(
                123, 'invalid!'
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=400,
                    message=contains_string('Invalid voicemail message ID'),
                    details=has_entry('message_id', 'invalid!'),
                )
            ),
        )

    def test_voicemail_delete_message_not_found(self):
        # voicemail not found
        assert_that(
            calling(self.calld_client.voicemails.delete_voicemail_message).with_args(
                123, 123
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail'),
                    details=has_entry('voicemail_id', 123),
                )
            ),
        )

        # message not found
        assert_that(
            calling(self.calld_client.voicemails.delete_voicemail_message).with_args(
                self._voicemail_id, 123
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail message'),
                    details=has_entry('message_id', '123'),
                )
            ),
        )

    def test_voicemail_delete_message_tenant_isolation(self):
        user_uuid_1 = str(uuid.uuid4())
        user_uuid_2 = str(uuid.uuid4())
        voicemail_id_1 = 111
        voicemail_id_2 = 222
        message_id_1 = '1724107750-00000011'  # Present in Docker image
        message_id_2 = '1724107750-00000021'  # Present in Docker image
        voicemail_1 = MockVoicemail(
            voicemail_id_1,
            '8001',
            'voicemail-name',
            'multitenant-1',
            tenant_uuid=VALID_TENANT_MULTITENANT_1,
        )
        voicemail_2 = MockVoicemail(
            voicemail_id_2,
            '8002',
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
        calld_1.voicemails.delete_voicemail_message(voicemail_id_1, message_id_1)
        self._assert_voicemail_message_deleted(calld_1, voicemail_id_1, message_id_1)

        # tenant 1, voicemail 2 = NOK
        assert_that(
            calling(calld_1.voicemails.delete_voicemail_message).with_args(
                voicemail_id_2, message_id_2
            ),
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
            calling(calld_2.voicemails.delete_voicemail_message).with_args(
                voicemail_id_1, message_id_2
            ),
            raises(CalldError).matching(
                has_properties(
                    status_code=404,
                    message=contains_string('No such voicemail'),
                    details=has_entry('voicemail_id', voicemail_id_1),
                )
            ),
        )

        # tenant 2, voicemail 2 = OK
        calld_2.voicemails.delete_voicemail_message(voicemail_id_2, message_id_2)
        self._assert_voicemail_message_deleted(calld_2, voicemail_id_2, message_id_2)

        # restore messages
        self.restart_service('volume-init')

    def test_voicemail_delete_message(self):
        self.calld_client.voicemails.delete_voicemail_message(
            self._voicemail_id, self._message_id
        )
        self._assert_voicemail_message_deleted(
            self.calld_client, self._voicemail_id, self._message_id
        )

        # restore message
        self.restart_service('volume-init')

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

    def test_voicemail_head_greeting(self):
        # see test_voicemail_greeting_workflow
        pass

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

    def test_voicemail_head_greeting_from_user(self):
        # see test_voicemail_greeting_workflow_from_user
        pass

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

    def test_voicemail_get_greeting(self):
        # see test_voicemail_greeting_workflow
        pass

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

    def test_voicemail_get_greeting_from_user(self):
        # see test_voicemail_greeting_workflow_from_user
        pass

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

    def test_voicemail_copy_greeting(self):
        # see test_voicemail_greeting_workflow
        pass

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

    def test_voicemail_put_greeting(self):
        # see test_voicemail_greeting_workflow
        pass

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

    def test_voicemail_put_greeting_from_user(self):
        # see test_voicemail_greeting_workflow_from_user
        pass

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

    def test_voicemail_create_greeting(self):
        # see test_voicemail_greeting_workflow
        pass

    def test_voicemail_create_from_user_invalid_body(self):
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

    def test_voicemail_create_greeting_from_user(self):
        # see test_voicemail_greeting_workflow_from_user
        pass

    def test_voicemail_greeting_workflow(self):
        user_uuid_other_tenant = str(uuid.uuid4())
        calld_other_tenant = self.make_user_calld(
            user_uuid_other_tenant, tenant_uuid=VALID_TENANT_MULTITENANT_2
        )

        # create greeting from other tenant = NOK
        with self._assert_voicemail_not_found():
            calld_other_tenant.voicemails.create_voicemail_greeting(
                self._voicemail_id, 'busy', WAVE_DATA_1
            )
        # create greeting
        self.calld_client.voicemails.create_voicemail_greeting(
            self._voicemail_id, 'busy', WAVE_DATA_1
        )

        # copy greeting from other tenant = NOK
        with self._assert_voicemail_not_found():
            calld_other_tenant.voicemails.copy_voicemail_greeting(
                self._voicemail_id, 'busy', 'unavailable'
            )
        # copy greeting
        self.calld_client.voicemails.copy_voicemail_greeting(
            self._voicemail_id, 'busy', 'unavailable'
        )
        self.calld_client.voicemails.copy_voicemail_greeting(
            self._voicemail_id, 'busy', 'name'
        )

        # create greeting but already exists = NOK
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
            # greeting exists from other tenant = NOK
            exists = calld_other_tenant.voicemails.voicemail_greeting_exists(
                self._voicemail_id, greeting
            )
            assert not exists

            # greeting exists
            exists = self.calld_client.voicemails.voicemail_greeting_exists(
                self._voicemail_id, greeting
            )
            assert exists

            # get greeting from other tenant = NOK
            with self._assert_voicemail_not_found():
                data = calld_other_tenant.voicemails.get_voicemail_greeting(
                    self._voicemail_id, greeting
                )
            # get greeting
            data = self.calld_client.voicemails.get_voicemail_greeting(
                self._voicemail_id, greeting
            )
            assert_that(data, equal_to(WAVE_DATA_1))

        # update greeting from other tenant = NOK
        with self._assert_voicemail_not_found():
            calld_other_tenant.voicemails.update_voicemail_greeting(
                self._voicemail_id, 'busy', WAVE_DATA_2
            )
        # update greeting
        self.calld_client.voicemails.update_voicemail_greeting(
            self._voicemail_id, 'busy', WAVE_DATA_2
        )
        data = self.calld_client.voicemails.get_voicemail_greeting(
            self._voicemail_id, 'busy'
        )
        assert_that(data, equal_to(WAVE_DATA_2))

        for greeting in VALID_GREETINGS:
            # delete greeting from other tenant = NOK
            with self._assert_voicemail_not_found():
                calld_other_tenant.voicemails.delete_voicemail_greeting(
                    self._voicemail_id, greeting
                )
            # delete greeting
            self.calld_client.voicemails.delete_voicemail_greeting(
                self._voicemail_id, greeting
            )
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

    @contextmanager
    def _assert_voicemail_not_found(self):
        with pytest.raises(CalldError) as exc_info:
            yield

        calld_error = exc_info.value
        assert calld_error.status_code == 404
        assert calld_error.error_id == 'no-such-voicemail'

    def _assert_voicemail_message_deleted(self, calld_client, voicemail_id, message_id):
        def message_deleted():
            assert_that(
                calling(calld_client.voicemails.get_voicemail_message).with_args(
                    voicemail_id, message_id
                ),
                raises(CalldError).matching(
                    has_properties(
                        status_code=404,
                        message=contains_string('No such voicemail message'),
                        details=has_entry('message_id', message_id),
                    )
                ),
            )

        until.assert_(
            message_deleted, message='Voicemail message is still present', timeout=5
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
