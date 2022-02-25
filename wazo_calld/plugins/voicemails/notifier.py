# Copyright 2022-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_bus.resources.voicemail.event import (
    CreateUserVoicemailMessageEvent,
    UpdateUserVoicemailMessageEvent,
    DeleteUserVoicemailMessageEvent,
)


class VoicemailsNotifier(object):
    def __init__(self, bus_publisher):
        self._bus_publisher = bus_publisher

    @staticmethod
    def _build_headers(user_uuids=None, **kwargs):
        headers = {}
        for uuid in user_uuids or []:
            headers[f'user_uuid:{uuid}'] = True

        for key, value in kwargs.items():
            if value:
                headers[key] = value
        return headers if headers else None

    def create_user_voicemail_message(
        self, user_uuid, tenant_uuid, voicemail_id, message_id, message
    ):
        event = CreateUserVoicemailMessageEvent(
            user_uuid, voicemail_id, message_id, message
        )
        headers = self._build_headers(user_uuids=[user_uuid], tenant_uuid=tenant_uuid)
        self._bus_publisher.publish(event, headers=headers)

    def update_user_voicemail_message(
        self, user_uuid, tenant_uuid, voicemail_id, message_id, message
    ):
        event = UpdateUserVoicemailMessageEvent(
            user_uuid, voicemail_id, message_id, message
        )
        headers = self._build_headers(user_uuids=[user_uuid], tenant_uuid=tenant_uuid)
        self._bus_publisher.publish(event, headers=headers)

    def delete_user_voicemail_message(
        self, user_uuid, tenant_uuid, voicemail_id, message_id, message
    ):
        event = DeleteUserVoicemailMessageEvent(
            user_uuid, voicemail_id, message_id, message
        )
        headers = self._build_headers(user_uuids=[user_uuid], tenant_uuid=tenant_uuid)
        self._bus_publisher.publish(event, headers=headers)
