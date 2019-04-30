# Copyright 2016-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from xivo_bus.resources.voicemail.event import (
    CreateUserVoicemailMessageEvent,
    UpdateUserVoicemailMessageEvent,
    DeleteUserVoicemailMessageEvent,
)

from .resources import voicemail_message_schema

logger = logging.getLogger(__name__)


class VoicemailsBusEventHandler:

    def __init__(self, confd_client, bus_publisher, voicemail_cache):
        # voicemail_cache must not be shared with other objects
        self._confd_client = confd_client
        self._bus_publisher = bus_publisher
        self._voicemail_cache = voicemail_cache

    def subscribe(self, bus_consumer):
        bus_consumer.on_ami_event('MessageWaiting', self._voicemail_updated)

    def _voicemail_updated(self, event):
        number, context = event['Mailbox'].split('@', 1)
        diff = self._voicemail_cache.get_diff(number, context)
        if diff.is_empty():
            return
        try:
            voicemail = self._get_voicemail(number, context)
            for user in voicemail['users']:
                for bus_msg in self._create_bus_msgs_from_diff(user['uuid'], voicemail['id'], diff):
                    self._bus_publisher.publish(bus_msg, headers={'user_uuid:{uuid}'.format(uuid=user['uuid']): True})
        except Exception:
            logger.exception('fail to publish voicemail message to bus')

    def _get_voicemail(self, number, context):
        response = self._confd_client.voicemails.list(number=number, context=context, recurse=True)
        return response['items'][0]

    def _create_bus_msgs_from_diff(self, user_uuid, voicemail_id, diff):
        for message_info in diff.created_messages:
            message_data = voicemail_message_schema.dump(message_info).data
            yield CreateUserVoicemailMessageEvent(user_uuid, voicemail_id, message_info['id'], message_data)
        for message_info in diff.updated_messages:
            message_data = voicemail_message_schema.dump(message_info).data
            yield UpdateUserVoicemailMessageEvent(user_uuid, voicemail_id, message_info['id'], message_data)
        for message_info in diff.deleted_messages:
            message_data = voicemail_message_schema.dump(message_info).data
            yield DeleteUserVoicemailMessageEvent(user_uuid, voicemail_id, message_info['id'], message_data)
