# Copyright 2016-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from wazo_bus.resources.call_logd.types import VoicemailTranscriptionDataDict
from wazo_bus.resources.voicemail.types import VoicemailTranscriptionCalldDataDict
from wazo_confd_client import Client as ConfdClient

from wazo_calld.bus import CoreBusConsumer

from .exceptions import VoicemailNotFound
from .notifier import VoicemailsNotifier
from .schemas import UnifiedVoicemailMessageSchema

if TYPE_CHECKING:
    from .storage import _VoicemailMessagesCache, _VoicemailMessagesDiff

logger = logging.getLogger(__name__)


VoicemailAccessType = Literal['personal', 'global']


class VoicemailUserDict(TypedDict):
    uuid: str


class VoicemailDict(TypedDict):
    id: int
    name: str
    accesstype: VoicemailAccessType
    tenant_uuid: str
    users: list[VoicemailUserDict]


voicemail_message_schema = UnifiedVoicemailMessageSchema()


class TranscriptionBusEventHandler:
    def __init__(self, confd_client: ConfdClient, notifier: VoicemailsNotifier):
        self._confd_client = confd_client
        self._notifier = notifier

    def subscribe(self, bus_consumer: CoreBusConsumer) -> None:
        bus_consumer.subscribe(
            'call_logd_voicemail_transcription_created',
            self._transcription_created,
        )
        bus_consumer.subscribe(
            'call_logd_voicemail_transcription_deleted',
            self._transcription_deleted,
        )

    def _transcription_created(self, event: VoicemailTranscriptionDataDict) -> None:
        voicemail = self._get_voicemail(event['voicemail_id'])
        transcription = VoicemailTranscriptionCalldDataDict(
            voicemail_id=event['voicemail_id'],
            message_id=event['message_id'],
            transcription_text=event['transcription_text'],
            provider_id=event['provider_id'],
            language=event['language'],
            duration=event['duration'],
            created_at=event['created_at'],
        )
        tenant_uuid = voicemail['tenant_uuid']

        match voicemail['accesstype']:
            case 'personal':
                for user in voicemail['users']:
                    self._notifier.create_user_voicemail_transcription(
                        user['uuid'], tenant_uuid, transcription
                    )
            case 'global':
                self._notifier.create_global_voicemail_transcription(
                    tenant_uuid, transcription
                )
            case _:
                logger.warning(
                    "Ignoring event for unsupported voicemail access type %s (voicemail id %s)",
                    voicemail['accesstype'],
                    voicemail['id'],
                )

    def _transcription_deleted(self, event: VoicemailTranscriptionDataDict) -> None:
        voicemail = self._get_voicemail(event['voicemail_id'])
        transcription = VoicemailTranscriptionCalldDataDict(
            voicemail_id=event['voicemail_id'],
            message_id=event['message_id'],
            transcription_text=event['transcription_text'],
            provider_id=event['provider_id'],
            language=event['language'],
            duration=event['duration'],
            created_at=event['created_at'],
        )
        tenant_uuid = voicemail['tenant_uuid']

        match voicemail['accesstype']:
            case 'personal':
                for user in voicemail['users']:
                    self._notifier.delete_user_voicemail_transcription(
                        user['uuid'], tenant_uuid, transcription
                    )
            case 'global':
                self._notifier.delete_global_voicemail_transcription(
                    tenant_uuid, transcription
                )
            case _:
                logger.warning(
                    "Ignoring event for unsupported voicemail access type %s (voicemail id %s)",
                    voicemail['accesstype'],
                    voicemail['id'],
                )

    def _get_voicemail(self, voicemail_id: int) -> VoicemailDict:
        return self._confd_client.voicemails.get(voicemail_id)


class VoicemailsBusEventHandler:
    def __init__(
        self,
        confd_client: ConfdClient,
        notifier: VoicemailsNotifier,
        voicemail_cache: _VoicemailMessagesCache,
    ):
        # voicemail_cache must not be shared with other objects
        self._confd_client = confd_client
        self._notifier = notifier
        self._voicemail_cache = voicemail_cache

    def subscribe(self, bus_consumer: CoreBusConsumer) -> None:
        bus_consumer.subscribe('MessageWaiting', self._voicemail_updated)

    def _voicemail_updated(self, event: dict[str, str]) -> None:
        number, context = event['Mailbox'].split('@', 1)
        diff = self._voicemail_cache.get_diff(number, context)
        if diff.is_empty():
            logger.debug("No change found for mailbox %s@%s", number, context)
            return
        voicemail = self._get_voicemail(number, context)
        match voicemail['accesstype']:
            case 'personal':
                self._send_users_notifications_from_diff(voicemail, diff)
            case 'global':
                self._send_tenant_notifications_from_diff(voicemail, diff)
            case _:
                logger.warning(
                    "Ignoring event for unsupported voicemail access type %s (voicemail id %s)",
                    voicemail['accesstype'],
                    voicemail['id'],
                )

    def _get_voicemail(self, number: str, context: str) -> VoicemailDict:
        response = self._confd_client.voicemails.list(
            number=number, context=context, recurse=True
        )
        items = response['items']
        if not items:
            raise VoicemailNotFound(number=number, context=context)
        return items[0]

    def _send_tenant_notifications_from_diff(
        self, voicemail: VoicemailDict, diff: _VoicemailMessagesDiff
    ) -> None:
        tenant_uuid = voicemail['tenant_uuid']

        for message in diff.created_messages:
            payload = _build_message(voicemail_message_schema, voicemail, message)
            self._notifier.create_global_voicemail_message(tenant_uuid, payload)

        for message in diff.updated_messages:
            payload = _build_message(voicemail_message_schema, voicemail, message)
            self._notifier.update_global_voicemail_message(tenant_uuid, payload)

        for message in diff.deleted_messages:
            payload = _build_message(voicemail_message_schema, voicemail, message)
            self._notifier.delete_global_voicemail_message(tenant_uuid, payload)

    def _send_users_notifications_from_diff(
        self, voicemail: VoicemailDict, diff: _VoicemailMessagesDiff
    ) -> None:
        tenant_uuid = voicemail['tenant_uuid']
        voicemail_id = voicemail['id']

        for user in voicemail['users']:
            user_uuid = user['uuid']

            for message in diff.created_messages:
                payload = _build_message(voicemail_message_schema, voicemail, message)
                self._notifier.create_user_voicemail_message(
                    user_uuid, tenant_uuid, voicemail_id, payload['id'], payload
                )

            for message in diff.updated_messages:
                payload = _build_message(voicemail_message_schema, voicemail, message)
                self._notifier.update_user_voicemail_message(
                    user_uuid, tenant_uuid, voicemail_id, payload['id'], payload
                )

            for message in diff.deleted_messages:
                payload = _build_message(voicemail_message_schema, voicemail, message)
                self._notifier.delete_user_voicemail_message(
                    user_uuid, tenant_uuid, voicemail_id, payload['id'], payload
                )


def _build_message(
    schema: UnifiedVoicemailMessageSchema,
    voicemail: VoicemailDict,
    message: dict[str, Any],
) -> dict:
    voicemail_info = {
        'id': voicemail['id'],
        'name': voicemail['name'],
        'accesstype': voicemail['accesstype'],
    }
    return schema.dump(message | {'voicemail': voicemail_info})
