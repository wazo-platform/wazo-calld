# Copyright 2022-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_bus.resources.push_notification.events import (
    CallCancelPushNotificationEvent,
    CallPushNotificationEvent,
)


class Notifier:
    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    def cancel_push_notification(self, payload, tenant_uuid, user_uuid):
        event = CallCancelPushNotificationEvent(payload, tenant_uuid, user_uuid)
        self._bus_producer.publish(event)

    def push_notification(self, payload, tenant_uuid, user_uuid):
        event = CallPushNotificationEvent(payload, tenant_uuid, user_uuid)
        self._bus_producer.publish(event)
