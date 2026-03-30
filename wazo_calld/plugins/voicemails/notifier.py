# Copyright 2022-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import TYPE_CHECKING

from wazo_bus.resources.voicemail.event import (
    GlobalVoicemailMessageCreatedEvent,
    GlobalVoicemailMessageDeletedEvent,
    GlobalVoicemailMessageUpdatedEvent,
    GlobalVoicemailTranscriptionCreatedEvent,
    GlobalVoicemailTranscriptionDeletedEvent,
    UserVoicemailMessageCreatedEvent,
    UserVoicemailMessageDeletedEvent,
    UserVoicemailMessageUpdatedEvent,
    UserVoicemailTranscriptionCreatedEvent,
    UserVoicemailTranscriptionDeletedEvent,
)

from wazo_calld.bus import CoreBusPublisher

if TYPE_CHECKING:
    from .bus_consume import VoicemailTranscriptionDict


class VoicemailsNotifier:
    def __init__(self, bus_publisher: CoreBusPublisher) -> None:
        self._bus_publisher = bus_publisher

    def create_user_voicemail_message(
        self,
        user_uuid: str,
        tenant_uuid: str,
        voicemail_id: int,
        message_id: str,
        message: dict,
    ) -> None:
        event = UserVoicemailMessageCreatedEvent(
            message_id, voicemail_id, message, tenant_uuid, user_uuid
        )
        self._bus_publisher.publish(event)

    def update_user_voicemail_message(
        self,
        user_uuid: str,
        tenant_uuid: str,
        voicemail_id: int,
        message_id: str,
        message: dict,
    ) -> None:
        event = UserVoicemailMessageUpdatedEvent(
            message_id, voicemail_id, message, tenant_uuid, user_uuid
        )
        self._bus_publisher.publish(event)

    def delete_user_voicemail_message(
        self,
        user_uuid: str,
        tenant_uuid: str,
        voicemail_id: int,
        message_id: str,
        message: dict,
    ) -> None:
        event = UserVoicemailMessageDeletedEvent(
            message_id, voicemail_id, message, tenant_uuid, user_uuid
        )
        self._bus_publisher.publish(event)

    def create_global_voicemail_message(self, tenant_uuid: str, message: dict) -> None:
        event = GlobalVoicemailMessageCreatedEvent(message, tenant_uuid)
        self._bus_publisher.publish(event)

    def update_global_voicemail_message(self, tenant_uuid: str, message: dict) -> None:
        event = GlobalVoicemailMessageUpdatedEvent(message, tenant_uuid)
        self._bus_publisher.publish(event)

    def delete_global_voicemail_message(self, tenant_uuid: str, message: dict) -> None:
        event = GlobalVoicemailMessageDeletedEvent(message, tenant_uuid)
        self._bus_publisher.publish(event)

    def create_user_voicemail_transcription(
        self,
        user_uuid: str,
        tenant_uuid: str,
        transcription: VoicemailTranscriptionDict,
    ) -> None:
        event = UserVoicemailTranscriptionCreatedEvent(
            transcription, tenant_uuid, user_uuid
        )
        self._bus_publisher.publish(event)

    def delete_user_voicemail_transcription(
        self,
        user_uuid: str,
        tenant_uuid: str,
        transcription: VoicemailTranscriptionDict,
    ) -> None:
        event = UserVoicemailTranscriptionDeletedEvent(
            transcription, tenant_uuid, user_uuid
        )
        self._bus_publisher.publish(event)

    def create_global_voicemail_transcription(
        self, tenant_uuid: str, transcription: VoicemailTranscriptionDict
    ) -> None:
        event = GlobalVoicemailTranscriptionCreatedEvent(transcription, tenant_uuid)
        self._bus_publisher.publish(event)

    def delete_global_voicemail_transcription(
        self, tenant_uuid: str, transcription: VoicemailTranscriptionDict
    ) -> None:
        event = GlobalVoicemailTranscriptionDeletedEvent(transcription, tenant_uuid)
        self._bus_publisher.publish(event)
