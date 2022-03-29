# -*- coding: utf-8 -*-
# Copyright 2018-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

logger = logging.getLogger(__name__)


class PushNotificationBusEventHandler(object):

    def __init__(self, notifier):
        self._notifier = notifier

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

        body = {
            'peer_caller_id_number': event["CallerIDNum"],
            'peer_caller_id_name': event["CallerIDName"],
            'call_id': event["Uniqueid"],
            'video': video_enabled
        }

        self._notifier.push_notification(body, tenant_uuid, user_uuid)
