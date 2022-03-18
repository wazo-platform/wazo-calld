# Copyright 2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

class MobilePushService:

    def __init__(self, notifier):
        self._notifier = notifier

    def send_push_notification(
        self,
        tenant_uuid,
        user_uuid,
        call_id,
        caller_id_name,
        caller_id_number,
        video_enabled,
    ):
        body = {
            'peer_caller_id_number': caller_id_number,
            'peer_caller_id_name': caller_id_name,
            'call_id': call_id,
            'video': video_enabled
        }

        self._notifier.push_notification(body, tenant_uuid, user_uuid)
