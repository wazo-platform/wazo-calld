# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock

from wazo_calld.plugins.voicemails.services import VoicemailsService


class TestEnrichMessagesWithTranscriptions:
    def _make_service(self, call_logd_client=None):
        ari = MagicMock()
        confd_client = MagicMock()
        storage = MagicMock()
        return VoicemailsService(ari, confd_client, storage, call_logd_client)

    def test_enrichment_success(self):
        call_logd_client = MagicMock()
        call_logd_client.voicemail_transcription.list_transcriptions.return_value = {
            'items': [
                {
                    'message_id': 'msg-1',
                    'transcription_text': 'Hello world',
                    'voicemail_id': 42,
                },
                {
                    'message_id': 'msg-2',
                    'transcription_text': 'Goodbye',
                    'voicemail_id': 42,
                },
            ],
            'total': 2,
            'filtered': 2,
        }
        service = self._make_service(call_logd_client)

        messages = [
            {'id': 'msg-1', 'duration': 10},
            {'id': 'msg-2', 'duration': 5},
            {'id': 'msg-3', 'duration': 3},
        ]
        service._enrich_messages_with_transcriptions(messages, {42})

        assert messages[0]['transcription'] == {'text': 'Hello world'}
        assert messages[1]['transcription'] == {'text': 'Goodbye'}
        assert 'transcription' not in messages[2]

    def test_enrichment_call_logd_unavailable(self):
        call_logd_client = MagicMock()
        call_logd_client.voicemail_transcription.list_transcriptions.side_effect = (
            Exception('connection refused')
        )
        service = self._make_service(call_logd_client)

        messages = [{'id': 'msg-1', 'duration': 10}]
        service._enrich_messages_with_transcriptions(messages, {42})

        assert 'transcription' not in messages[0]

    def test_enrichment_no_call_logd_client(self):
        service = self._make_service(call_logd_client=None)

        messages = [{'id': 'msg-1', 'duration': 10}]
        service._enrich_messages_with_transcriptions(messages, {42})

        assert 'transcription' not in messages[0]

    def test_enrichment_empty_messages(self):
        call_logd_client = MagicMock()
        service = self._make_service(call_logd_client)

        messages: list[dict] = []
        service._enrich_messages_with_transcriptions(messages, {42})

        call_logd_client.voicemail_transcription.list_transcriptions.assert_not_called()

    def test_enrichment_no_voicemail_ids(self):
        call_logd_client = MagicMock()
        service = self._make_service(call_logd_client)

        messages = [{'id': 'msg-1'}]
        service._enrich_messages_with_transcriptions(messages, set())

        call_logd_client.voicemail_transcription.list_transcriptions.assert_not_called()
