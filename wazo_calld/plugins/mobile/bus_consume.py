# -*- coding: utf-8 -*-
# Copyright 2018-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

logger = logging.getLogger(__name__)


class PushNotificationBusEventHandler(object):

    def __init__(self, service):
        self._service = service

    def subscribe(self, bus_consumer):
        bus_consumer.subscribe('UserEvent', self._user_event)

    def _user_event(self, event):
        if event['UserEvent'] != 'Pushmobile':
            return

        user_uuid = event['WAZO_DST_UUID']
        video_enabled = event['WAZO_VIDEO_ENABLED'] == '1'
        tenant_uuid = event.get('ChanVariable', {}).get('WAZO_TENANT_UUID')

        logger.info(
            'Received push notification request for user %s from %s <%s>',
            user_uuid, event["CallerIDName"], event["CallerIDNum"],
        )

        self._service.send_push_notification(
            tenant_uuid,
            user_uuid,
            event["Uniqueid"],
            event["CallerIDName"],
            event["CallerIDNum"],
            video_enabled,
        )
