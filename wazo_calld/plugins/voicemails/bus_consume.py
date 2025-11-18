# Copyright 2016-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from .schemas import UnifiedVoicemailMessageSchema

logger = logging.getLogger(__name__)
voicemail_message_schema = UnifiedVoicemailMessageSchema()


class VoicemailsBusEventHandler:
    def __init__(self, confd_client, notifier, voicemail_cache):
        # voicemail_cache must not be shared with other objects
        self._confd_client = confd_client
        self._notifier = notifier
        self._voicemail_cache = voicemail_cache

    def subscribe(self, bus_consumer):
        bus_consumer.subscribe('MessageWaiting', self._voicemail_updated)

    def _voicemail_updated(self, event):
        number, context = event['Mailbox'].split('@', 1)
        diff = self._voicemail_cache.get_diff(number, context)
        if diff.is_empty():
            return
        voicemail = self._get_voicemail(number, context)
        match voicemail['accesstype']:
            case 'personal':
                self._send_users_notifications_from_diff(voicemail, diff)
            case 'global':
                self._send_tenant_notifications_from_diff(voicemail, diff)
            case _:
                pass

    def _get_voicemail(self, number, context):
        response = self._confd_client.voicemails.list(
            number=number, context=context, recurse=True
        )
        return response['items'][0]

    def _send_tenant_notifications_from_diff(self, voicemail, diff):
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

    def _send_users_notifications_from_diff(self, voicemail, diff):
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


def _build_message(schema, voicemail, message) -> dict:
    voicemail_info = {
        'id': voicemail['id'],
        'name': voicemail['name'],
        'accesstype': voicemail['accesstype'],
    }
    return schema.dump(message | {'voicemail': voicemail_info})
