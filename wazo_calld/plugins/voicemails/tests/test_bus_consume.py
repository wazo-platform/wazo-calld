# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock

from wazo_calld.plugins.voicemails.bus_consume import TranscriptionBusEventHandler


class TestTranscriptionBusEventHandler:
    def setup_method(self):
        self.confd_client = MagicMock()
        self.notifier = MagicMock()
        self.handler = TranscriptionBusEventHandler(self.confd_client, self.notifier)

    def _make_event(self, **overrides):
        event = {
            'voicemail_id': 42,
            'message_id': 'msg-1',
            'transcription_text': 'Hello world',
            'provider_id': 'openai/whisper-1',
            'language': 'en',
            'duration': 10.5,
            'created_at': '2026-03-12T10:00:00+00:00',
        }
        event.update(overrides)
        return event

    def _setup_personal_voicemail(self):
        self.confd_client.voicemails.get.return_value = {
            'id': 42,
            'tenant_uuid': 'tenant-1',
            'accesstype': 'personal',
            'users': [{'uuid': 'user-1'}, {'uuid': 'user-2'}],
        }

    def _setup_global_voicemail(self):
        self.confd_client.voicemails.get.return_value = {
            'id': 42,
            'tenant_uuid': 'tenant-1',
            'accesstype': 'global',
            'users': [],
        }

    def test_personal_voicemail_transcription_created(self):
        self._setup_personal_voicemail()
        event = self._make_event()

        self.handler._transcription_created(event)

        assert self.notifier.create_user_voicemail_transcription.call_count == 2
        self.notifier.create_user_voicemail_transcription.assert_any_call(
            'user-1',
            'tenant-1',
            {
                'voicemail_id': 42,
                'message_id': 'msg-1',
                'transcription_text': 'Hello world',
                'provider_id': 'openai/whisper-1',
                'language': 'en',
                'duration': 10.5,
                'created_at': '2026-03-12T10:00:00+00:00',
            },
        )

    def test_personal_voicemail_transcription_deleted(self):
        self._setup_personal_voicemail()
        event = self._make_event()

        self.handler._transcription_deleted(event)

        assert self.notifier.delete_user_voicemail_transcription.call_count == 2

    def test_global_voicemail_transcription_created(self):
        self._setup_global_voicemail()
        event = self._make_event()

        self.handler._transcription_created(event)

        self.notifier.create_global_voicemail_transcription.assert_called_once_with(
            'tenant-1',
            {
                'voicemail_id': 42,
                'message_id': 'msg-1',
                'transcription_text': 'Hello world',
                'provider_id': 'openai/whisper-1',
                'language': 'en',
                'duration': 10.5,
                'created_at': '2026-03-12T10:00:00+00:00',
            },
        )

    def test_global_voicemail_transcription_deleted(self):
        self._setup_global_voicemail()
        event = self._make_event()

        self.handler._transcription_deleted(event)

        self.notifier.delete_global_voicemail_transcription.assert_called_once()
