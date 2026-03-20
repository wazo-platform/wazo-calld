# Copyright 2022-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from wazo_bus.resources.push_notification.events import (
    CallCancelPushNotificationEvent,
    CallPushNotificationEvent,
)

logger = logging.getLogger(__name__)


class Notifier:
    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    def cancel_push_notification(self, payload, tenant_uuid, user_uuid):
        logger.info(
            'Publishing cancel push notification push_trace_uuid=%s user=%s',
            payload.get('push_trace_uuid', ''),
            user_uuid,
        )
        event = CallCancelPushNotificationEvent(payload, tenant_uuid, user_uuid)
        self._bus_producer.publish(event)

    def push_notification(self, payload, tenant_uuid, user_uuid):
        logger.info(
            'Publishing push notification event push_trace_uuid=%s user=%s',
            payload.get('push_trace_uuid', ''),
            user_uuid,
        )
        event = CallPushNotificationEvent(payload, tenant_uuid, user_uuid)
        self._bus_producer.publish(event)
