# Copyright 2016-2022 The Wazo Authors  (see the AUTHORS file)
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
        for user in voicemail['users']:
            self._send_notifications_from_diff(
                user['uuid'], voicemail['tenant_uuid'], voicemail['id'], diff
            )

    def _get_voicemail(self, number, context):
        response = self._confd_client.voicemails.list(
            number=number, context=context, recurse=True
        )
        return response['items'][0]

    def _send_notifications_from_diff(self, user_uuid, tenant_uuid, voicemail_id, diff):
        for message in diff.created_messages:
            payload = voicemail_message_schema.dump(message)
            self._notifier.create_user_voicemail_message(
                user_uuid, tenant_uuid, voicemail_id, payload['id'], payload
            )

        for message in diff.updated_messages:
            payload = voicemail_message_schema.dump(message)
            self._notifier.update_user_voicemail_message(
                user_uuid, tenant_uuid, voicemail_id, payload['id'], payload
            )

        for message in diff.deleted_messages:
            payload = voicemail_message_schema.dump(message)
            self._notifier.delete_user_voicemail_message(
                user_uuid, tenant_uuid, voicemail_id, payload['id'], payload
            )
