# Copyright 2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_bus.resources.push_notification.events import PushNotificationEvent


class Notifier:
    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    @staticmethod
    def _build_headers(tenant_uuid, user_uuids=None):
        headers = {'tenant_uuid': tenant_uuid}
        for uuid in user_uuids or []:
            headers[f'user_uuid:{uuid}'] = True

        return headers

    def push_notification(self, push_notification, tenant_uuid, user_uuid):
        event = PushNotificationEvent(push_notification, user_uuid)
        headers = self._build_headers(tenant_uuid, user_uuids=[user_uuid])
        self._bus_producer.publish(event, headers=headers)
