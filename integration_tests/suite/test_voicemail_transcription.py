# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import uuid

from hamcrest import (
    assert_that,
    has_entries,
    has_item,
    has_items,
    is_,
    none,
    only_contains,
)
from wazo_test_helpers import until

from .helpers.base import IntegrationTest
from .helpers.confd import MockVoicemail
from .helpers.constants import VALID_TENANT, VALID_TENANT_MULTITENANT_1, XIVO_UUID
from .helpers.real_asterisk import RealAsteriskIntegrationTest
from .helpers.wait_strategy import CalldEverythingOkWaitStrategy


class TestVoicemailTranscriptionBusConsume(IntegrationTest):
    asset = 'real_asterisk'
    wait_strategy = CalldEverythingOkWaitStrategy()

    def setUp(self):
        super().setUp()
        self.confd.reset()

    def test_personal_voicemail_transcription_created_event(self):
        user_uuid_1 = str(uuid.uuid4())
        user_uuid_2 = str(uuid.uuid4())
        voicemail_id = 111
        message_id = 'msg-001'
        voicemail = MockVoicemail(
            voicemail_id,
            '8000',
            'personal-vm',
            'default',
            user_uuids=[user_uuid_1, user_uuid_2],
            accesstype='personal',
            tenant_uuid=VALID_TENANT,
        )
        self.confd.set_voicemails(voicemail)

        events = self.bus.accumulator(
            headers={'name': 'user_voicemail_transcription_created'}
        )
        self.bus.send_voicemail_transcription_created_event(
            voicemail_id=voicemail_id,
            message_id=message_id,
            tenant_uuid=VALID_TENANT,
            transcription_text='Hello world',
            provider_id='openai/whisper-1',
            language='en',
            duration=10.5,
            created_at='2026-03-12T10:00:00+00:00',
        )

        def assert_fn():
            accumulated = events.accumulate()
            assert_that(
                accumulated,
                has_items(
                    has_entries(
                        name='user_voicemail_transcription_created',
                        origin_uuid=XIVO_UUID,
                        data=has_entries(
                            user_uuid=user_uuid_1,
                            voicemail_id=voicemail_id,
                            message_id=message_id,
                            transcription_text='Hello world',
                            provider_id='openai/whisper-1',
                            language='en',
                        ),
                    ),
                    has_entries(
                        name='user_voicemail_transcription_created',
                        origin_uuid=XIVO_UUID,
                        data=has_entries(
                            user_uuid=user_uuid_2,
                            voicemail_id=voicemail_id,
                            message_id=message_id,
                            transcription_text='Hello world',
                        ),
                    ),
                ),
            )

        until.assert_(assert_fn, tries=5)

    def test_global_voicemail_transcription_created_event(self):
        voicemail_id = 222
        message_id = 'msg-002'
        voicemail = MockVoicemail(
            voicemail_id,
            '8000',
            'global-vm',
            'default',
            accesstype='global',
            tenant_uuid=VALID_TENANT_MULTITENANT_1,
        )
        self.confd.set_voicemails(voicemail)

        events = self.bus.accumulator(
            headers={'name': 'global_voicemail_transcription_created'}
        )
        self.bus.send_voicemail_transcription_created_event(
            voicemail_id=voicemail_id,
            message_id=message_id,
            tenant_uuid=VALID_TENANT_MULTITENANT_1,
            transcription_text='Goodbye world',
            provider_id='openai/whisper-1',
            language='en',
            duration=5.0,
            created_at='2026-03-12T11:00:00+00:00',
        )

        def assert_fn():
            assert_that(
                events.accumulate(),
                has_item(
                    has_entries(
                        name='global_voicemail_transcription_created',
                        origin_uuid=XIVO_UUID,
                        data=has_entries(
                            voicemail_id=voicemail_id,
                            message_id=message_id,
                            transcription_text='Goodbye world',
                            provider_id='openai/whisper-1',
                            language='en',
                            duration=5.0,
                            created_at='2026-03-12T11:00:00+00:00',
                        ),
                    )
                ),
            )

        until.assert_(assert_fn, tries=5)


class TestVoicemailTranscriptionEnrichment(RealAsteriskIntegrationTest):
    asset = 'real_asterisk_call_logd'

    def setUp(self):
        super().setUp()
        self.confd.reset()
        self.call_logd.reset()

    def test_list_user_messages_with_transcription(self):
        user_uuid = str(uuid.uuid4())
        voicemail_id = 111
        message_id = '1724107750-00000001'  # Present in Docker volume
        voicemail = MockVoicemail(
            voicemail_id,
            '8000',
            'user-voicemail',
            'default',
            user_uuids=[user_uuid],
            tenant_uuid=VALID_TENANT,
        )
        self.confd.set_user_voicemails({user_uuid: [voicemail]})
        self.confd.set_voicemails(voicemail)

        self.call_logd.set_transcriptions(
            [
                {
                    'message_id': message_id,
                    'voicemail_id': voicemail_id,
                    'tenant_uuid': VALID_TENANT,
                    'transcription_text': 'This is a test transcription',
                    'provider_id': 'openai/whisper-1',
                    'language': 'en',
                    'duration': 19.0,
                },
            ]
        )

        calld = self.make_user_calld(user_uuid, tenant_uuid=VALID_TENANT)
        result = calld.voicemails.list_voicemail_messages_from_user(
            voicemail_type='personal'
        )

        assert_that(
            result,
            has_entries(
                items=has_item(
                    has_entries(
                        id=message_id,
                        transcription=has_entries(
                            text='This is a test transcription',
                        ),
                    ),
                ),
            ),
        )

    def test_list_user_messages_without_transcription(self):
        user_uuid = str(uuid.uuid4())
        voicemail_id = 111
        message_id = '1724107750-00000001'  # Present in Docker volume
        voicemail = MockVoicemail(
            voicemail_id,
            '8000',
            'user-voicemail',
            'default',
            user_uuids=[user_uuid],
            tenant_uuid=VALID_TENANT,
        )
        self.confd.set_user_voicemails({user_uuid: [voicemail]})
        self.confd.set_voicemails(voicemail)
        # No transcriptions set in call-logd
        calld = self.make_user_calld(user_uuid, tenant_uuid=VALID_TENANT)
        result = calld.voicemails.list_voicemail_messages_from_user(
            voicemail_type='personal'
        )

        assert_that(
            result,
            has_entries(
                items=has_item(
                    has_entries(
                        id=message_id,
                        transcription=is_(none()),
                    ),
                ),
            ),
        )

    def test_get_user_message_with_transcription(self):
        user_uuid = str(uuid.uuid4())
        voicemail_id = 111
        message_id = '1724107750-00000001'  # Present in Docker volume
        voicemail = MockVoicemail(
            voicemail_id,
            '8000',
            'user-voicemail',
            'default',
            user_uuids=[user_uuid],
            tenant_uuid=VALID_TENANT,
        )
        self.confd.set_user_voicemails({user_uuid: [voicemail]})
        self.confd.set_voicemails(voicemail)

        self.call_logd.set_transcriptions(
            [
                {
                    'message_id': message_id,
                    'voicemail_id': voicemail_id,
                    'tenant_uuid': VALID_TENANT,
                    'transcription_text': 'Hello from voicemail',
                    'provider_id': 'openai/whisper-1',
                    'language': 'en',
                    'duration': 19.0,
                },
            ]
        )

        calld = self.make_user_calld(user_uuid, tenant_uuid=VALID_TENANT)
        result = calld.voicemails.get_voicemail_message_from_user(message_id)

        assert_that(
            result,
            has_entries(
                id=message_id,
                transcription=has_entries(
                    text='Hello from voicemail',
                ),
            ),
        )

    def test_get_voicemail_message_with_transcription(self):
        voicemail_id = 111
        message_id = '1724107750-00000001'  # Present in Docker volume
        voicemail = MockVoicemail(
            voicemail_id,
            '8000',
            'admin-voicemail',
            'default',
            tenant_uuid=VALID_TENANT,
        )
        self.confd.set_voicemails(voicemail)

        self.call_logd.set_transcriptions(
            [
                {
                    'message_id': message_id,
                    'voicemail_id': voicemail_id,
                    'tenant_uuid': VALID_TENANT,
                    'transcription_text': 'Admin transcription',
                    'provider_id': 'openai/whisper-1',
                    'language': 'en',
                    'duration': 19.0,
                },
            ]
        )

        result = self.calld_client.voicemails.get_voicemail_message(
            voicemail_id, message_id
        )

        assert_that(
            result,
            has_entries(
                id=message_id,
                transcription=has_entries(
                    text='Admin transcription',
                ),
            ),
        )

    def test_get_voicemail_with_transcription(self):
        voicemail_id = 111
        message_id = '1724107750-00000001'  # Present in Docker volume
        voicemail = MockVoicemail(
            voicemail_id,
            '8000',
            'admin-voicemail',
            'default',
            tenant_uuid=VALID_TENANT,
        )
        self.confd.set_voicemails(voicemail)

        self.call_logd.set_transcriptions(
            [
                {
                    'message_id': message_id,
                    'voicemail_id': voicemail_id,
                    'tenant_uuid': VALID_TENANT,
                    'transcription_text': 'Voicemail transcription',
                    'provider_id': 'openai/whisper-1',
                    'language': 'en',
                    'duration': 19.0,
                },
            ]
        )

        result = self.calld_client.voicemails.get_voicemail(voicemail_id)

        assert_that(
            result,
            has_entries(
                id=voicemail_id,
                folders=has_item(
                    has_entries(
                        messages=has_item(
                            has_entries(
                                id=message_id,
                                transcription=has_entries(
                                    text='Voicemail transcription',
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )

    def test_get_voicemail_folder_with_transcription(self):
        voicemail_id = 111
        message_id = '1724107750-00000001'  # Present in Docker volume
        folder_id = 1  # INBOX
        voicemail = MockVoicemail(
            voicemail_id,
            '8000',
            'admin-voicemail',
            'default',
            tenant_uuid=VALID_TENANT,
        )
        self.confd.set_voicemails(voicemail)

        self.call_logd.set_transcriptions(
            [
                {
                    'message_id': message_id,
                    'voicemail_id': voicemail_id,
                    'tenant_uuid': VALID_TENANT,
                    'transcription_text': 'Folder transcription',
                    'provider_id': 'openai/whisper-1',
                    'language': 'en',
                    'duration': 19.0,
                },
            ]
        )

        result = self.calld_client.voicemails.get_voicemail_folder(
            voicemail_id, folder_id
        )

        assert_that(
            result,
            has_entries(
                messages=has_item(
                    has_entries(
                        id=message_id,
                        transcription=has_entries(
                            text='Folder transcription',
                        ),
                    ),
                ),
            ),
        )

    def test_get_user_voicemail_with_transcription(self):
        user_uuid = str(uuid.uuid4())
        voicemail_id = 111
        message_id = '1724107750-00000001'  # Present in Docker volume
        voicemail = MockVoicemail(
            voicemail_id,
            '8000',
            'user-voicemail',
            'default',
            user_uuids=[user_uuid],
            tenant_uuid=VALID_TENANT,
        )
        self.confd.set_user_voicemails({user_uuid: [voicemail]})
        self.confd.set_voicemails(voicemail)

        self.call_logd.set_transcriptions(
            [
                {
                    'message_id': message_id,
                    'voicemail_id': voicemail_id,
                    'tenant_uuid': VALID_TENANT,
                    'transcription_text': 'User voicemail transcription',
                    'provider_id': 'openai/whisper-1',
                    'language': 'en',
                    'duration': 19.0,
                },
            ]
        )

        calld = self.make_user_calld(user_uuid, tenant_uuid=VALID_TENANT)
        result = calld.voicemails.get_voicemail_from_user()

        assert_that(
            result,
            has_entries(
                folders=has_item(
                    has_entries(
                        messages=has_item(
                            has_entries(
                                id=message_id,
                                transcription=has_entries(
                                    text='User voicemail transcription',
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        )

    def test_get_user_voicemail_folder_with_transcription(self):
        user_uuid = str(uuid.uuid4())
        voicemail_id = 111
        message_id = '1724107750-00000001'  # Present in Docker volume
        folder_id = 1  # INBOX
        voicemail = MockVoicemail(
            voicemail_id,
            '8000',
            'user-voicemail',
            'default',
            user_uuids=[user_uuid],
            tenant_uuid=VALID_TENANT,
        )
        self.confd.set_user_voicemails({user_uuid: [voicemail]})
        self.confd.set_voicemails(voicemail)

        self.call_logd.set_transcriptions(
            [
                {
                    'message_id': message_id,
                    'voicemail_id': voicemail_id,
                    'tenant_uuid': VALID_TENANT,
                    'transcription_text': 'User folder transcription',
                    'provider_id': 'openai/whisper-1',
                    'language': 'en',
                    'duration': 19.0,
                },
            ]
        )

        calld = self.make_user_calld(user_uuid, tenant_uuid=VALID_TENANT)
        result = calld.voicemails.get_voicemail_folder_from_user(folder_id)

        assert_that(
            result,
            has_entries(
                messages=has_item(
                    has_entries(
                        id=message_id,
                        transcription=has_entries(
                            text='User folder transcription',
                        ),
                    ),
                ),
            ),
        )

    def test_list_admin_messages_with_transcription(self):
        user_uuid = str(uuid.uuid4())
        voicemail_id = 111
        message_id = '1724107750-00000001'  # Present in Docker volume
        voicemail = MockVoicemail(
            voicemail_id,
            '8000',
            'admin-voicemail',
            'default',
            tenant_uuid=VALID_TENANT,
        )
        self.confd.set_voicemails(voicemail)

        self.call_logd.set_transcriptions(
            [
                {
                    'message_id': message_id,
                    'voicemail_id': voicemail_id,
                    'tenant_uuid': VALID_TENANT,
                    'transcription_text': 'Admin list transcription',
                    'provider_id': 'openai/whisper-1',
                    'language': 'en',
                    'duration': 19.0,
                },
            ]
        )

        calld = self.make_user_calld(user_uuid, tenant_uuid=VALID_TENANT)
        result = calld.voicemails.list_voicemail_messages()

        items = result['items']
        msg = next(m for m in items if m['id'] == message_id)
        assert_that(
            msg.keys(),
            only_contains(
                'id',
                'caller_id_name',
                'caller_id_num',
                'duration',
                'timestamp',
                'empty',
                'transcripted',
                'voicemail',
                'folder',
            ),
        )
        assert_that(msg['transcripted'], is_(True))

    def test_list_admin_messages_without_transcription(self):
        user_uuid = str(uuid.uuid4())
        voicemail_id = 111
        message_id = '1724107750-00000001'  # Present in Docker volume
        voicemail = MockVoicemail(
            voicemail_id,
            '8000',
            'admin-voicemail',
            'default',
            tenant_uuid=VALID_TENANT,
        )
        self.confd.set_voicemails(voicemail)

        calld = self.make_user_calld(user_uuid, tenant_uuid=VALID_TENANT)
        result = calld.voicemails.list_voicemail_messages()

        items = result['items']
        msg = next(m for m in items if m['id'] == message_id)
        assert_that(
            msg.keys(),
            only_contains(
                'id',
                'caller_id_name',
                'caller_id_num',
                'duration',
                'timestamp',
                'empty',
                'transcripted',
                'voicemail',
                'folder',
            ),
        )
        assert_that(msg['transcripted'], is_(False))

    def test_list_user_messages_transcription_fault_tolerance(self):
        """Verify that messages are still returned when call-logd is unavailable."""
        user_uuid = str(uuid.uuid4())
        voicemail_id = 111
        message_id = '1724107750-00000001'  # Present in Docker volume
        voicemail = MockVoicemail(
            voicemail_id,
            '8000',
            'user-voicemail',
            'default',
            user_uuids=[user_uuid],
            tenant_uuid=VALID_TENANT,
        )
        self.confd.set_user_voicemails({user_uuid: [voicemail]})
        self.confd.set_voicemails(voicemail)

        calld = self.make_user_calld(user_uuid, tenant_uuid=VALID_TENANT)

        self.stop_service('call-logd')
        try:
            result = calld.voicemails.list_voicemail_messages_from_user(
                voicemail_type='personal'
            )
            assert_that(
                result,
                has_entries(
                    items=has_item(
                        has_entries(
                            id=message_id,
                            transcription=is_(none()),
                        ),
                    ),
                ),
            )
        finally:
            self.start_service('call-logd')
            self.reset_clients()

    def test_personal_voicemail_transcription_deleted_event(self):
        user_uuid_1 = str(uuid.uuid4())
        voicemail_id = 111
        message_id = 'msg-deleted-001'
        voicemail = MockVoicemail(
            voicemail_id,
            '8000',
            'personal-vm',
            'default',
            user_uuids=[user_uuid_1],
            accesstype='personal',
            tenant_uuid=VALID_TENANT,
        )
        self.confd.set_voicemails(voicemail)

        self.call_logd.set_transcriptions(
            [
                {
                    'message_id': message_id,
                    'voicemail_id': voicemail_id,
                    'tenant_uuid': VALID_TENANT,
                    'transcription_text': 'To be deleted',
                    'provider_id': 'openai/whisper-1',
                    'language': 'en',
                    'duration': 5.0,
                },
            ]
        )

        events = self.bus.accumulator(
            headers={'name': 'user_voicemail_transcription_deleted'}
        )
        self.call_logd.reset()

        def assert_fn():
            assert_that(
                events.accumulate(),
                has_item(
                    has_entries(
                        name='user_voicemail_transcription_deleted',
                        origin_uuid=XIVO_UUID,
                        data=has_entries(
                            user_uuid=user_uuid_1,
                            voicemail_id=voicemail_id,
                            message_id=message_id,
                            transcription_text='To be deleted',
                            provider_id='openai/whisper-1',
                            language='en',
                            duration=5.0,
                        ),
                    )
                ),
            )

        until.assert_(assert_fn, tries=5)

    def test_global_voicemail_transcription_deleted_event(self):
        voicemail_id = 111
        message_id = 'msg-deleted-002'
        voicemail = MockVoicemail(
            voicemail_id,
            '8000',
            'global-vm',
            'default',
            accesstype='global',
            tenant_uuid=VALID_TENANT,
        )
        self.confd.set_voicemails(voicemail)

        self.call_logd.set_transcriptions(
            [
                {
                    'message_id': message_id,
                    'voicemail_id': voicemail_id,
                    'tenant_uuid': VALID_TENANT,
                    'transcription_text': 'Global to be deleted',
                    'provider_id': 'openai/whisper-1',
                    'language': 'en',
                    'duration': 5.0,
                },
            ]
        )

        events = self.bus.accumulator(
            headers={'name': 'global_voicemail_transcription_deleted'}
        )
        self.call_logd.reset()

        def assert_fn():
            assert_that(
                events.accumulate(),
                has_item(
                    has_entries(
                        name='global_voicemail_transcription_deleted',
                        origin_uuid=XIVO_UUID,
                        data=has_entries(
                            voicemail_id=voicemail_id,
                            message_id=message_id,
                            transcription_text='Global to be deleted',
                            provider_id='openai/whisper-1',
                            language='en',
                            duration=5.0,
                        ),
                    )
                ),
            )

        until.assert_(assert_fn, tries=5)
