# Copyright 2016-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from .http import voicemail_message_schema

logger = logging.getLogger(__name__)


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
        users = []
        match voicemail['accesstype']:
            case 'personal':
                users = voicemail['users']
            case 'global':
                users = self._confd_client.users.list(context=context)['items']

        for user in users:
            self._send_notifications_from_diff(
                user['uuid'], voicemail['tenant_uuid'], voicemail['id'], diff
            )

    def _get_voicemail(self, number, context):
        response = self._confd_client.voicemails.list(
            number=number, context=context, recurse=True
        )
        return response['items'][0]

    def _send_notifications_from_diff(self, user_uuid, tenant_uuid, voicemail_id, diff):
        voicemail = self._confd_client.voicemails.get(
            voicemail_id, tenant_uuid=tenant_uuid
        )
        access_type = voicemail['accesstype']
        for message in diff.created_messages:
            payload = voicemail_message_schema.dump(message)
            match access_type:
                case 'personal':
                    self._notifier.create_user_voicemail_message(
                        user_uuid, tenant_uuid, voicemail_id, payload['id'], payload
                    )
                case 'global':
                    self._notifier.create_global_voicemail_message(
                        user_uuid, tenant_uuid, voicemail_id, payload['id'], payload
                    )
                case _:
                    logger.error(
                        f'unknown accesstype "{access_type}" for voicemail {voicemail_id}'
                    )

        for message in diff.updated_messages:
            payload = voicemail_message_schema.dump(message)
            match access_type:
                case 'personal':
                    self._notifier.update_user_voicemail_message(
                        user_uuid, tenant_uuid, voicemail_id, payload['id'], payload
                    )
                case 'global':
                    self._notifier.update_global_voicemail_message(
                        user_uuid, tenant_uuid, voicemail_id, payload['id'], payload
                    )
                case _:
                    logger.error(
                        f'unknown accesstype "{access_type}" for voicemail {voicemail_id}'
                    )

        for message in diff.deleted_messages:
            payload = voicemail_message_schema.dump(message)
            match access_type:
                case 'personal':
                    self._notifier.delete_user_voicemail_message(
                        user_uuid, tenant_uuid, voicemail_id, payload['id'], payload
                    )
                case 'global':
                    self._notifier.delete_global_voicemail_message(
                        user_uuid, tenant_uuid, voicemail_id, payload['id'], payload
                    )
                case _:
                    logger.error(
                        f'unknown accesstype "{access_type}" for voicemail {voicemail_id}'
                    )
