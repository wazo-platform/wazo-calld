# Copyright 2022-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_bus.resources.voicemail.event import (
    GlobalVoicemailMessageCreatedEvent,
    GlobalVoicemailMessageDeletedEvent,
    GlobalVoicemailMessageUpdatedEvent,
    UserVoicemailMessageCreatedEvent,
    UserVoicemailMessageDeletedEvent,
    UserVoicemailMessageUpdatedEvent,
)


class VoicemailsNotifier:
    def __init__(self, bus_publisher):
        self._bus_publisher = bus_publisher

    def create_user_voicemail_message(
        self, user_uuid, tenant_uuid, voicemail_id, message_id, message
    ):
        event = UserVoicemailMessageCreatedEvent(
            message_id, voicemail_id, message, tenant_uuid, user_uuid
        )
        self._bus_publisher.publish(event)

    def update_user_voicemail_message(
        self, user_uuid, tenant_uuid, voicemail_id, message_id, message
    ):
        event = UserVoicemailMessageUpdatedEvent(
            message_id, voicemail_id, message, tenant_uuid, user_uuid
        )
        self._bus_publisher.publish(event)

    def delete_user_voicemail_message(
        self, user_uuid, tenant_uuid, voicemail_id, message_id, message
    ):
        event = UserVoicemailMessageDeletedEvent(
            message_id, voicemail_id, message, tenant_uuid, user_uuid
        )
        self._bus_publisher.publish(event)

    def create_global_voicemail_message(self, tenant_uuid, message):
        event = GlobalVoicemailMessageCreatedEvent(message, tenant_uuid)
        self._bus_publisher.publish(event)

    def update_global_voicemail_message(self, tenant_uuid, message):
        event = GlobalVoicemailMessageUpdatedEvent(message, tenant_uuid)
        self._bus_publisher.publish(event)

    def delete_global_voicemail_message(self, tenant_uuid, message):
        event = GlobalVoicemailMessageDeletedEvent(message, tenant_uuid)
        self._bus_publisher.publish(event)
