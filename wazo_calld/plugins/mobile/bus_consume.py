# -*- coding: utf-8 -*-
# Copyright 2018-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo_bus.resources.common.event import ArbitraryEvent


logger = logging.getLogger(__name__)


class PushNotificationBusEventHandler(object):

    def __init__(self, bus_publisher):
        self.bus_publisher = bus_publisher

    def subscribe(self, bus_consumer):
        bus_consumer.on_ami_event('UserEvent', self._user_event)

    def _user_event(self, event):
        if event['UserEvent'] != 'Pushmobile':
            return

        user_uuid = event['WAZO_DST_UUID']
        video_enabled = event['WAZO_VIDEO_ENABLED'] == '1'

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

        bus_event = ArbitraryEvent(
            name='call_push_notification',
            body=body,
            required_acl='events.calls.{}'.format(user_uuid)
        )
        bus_event.routing_key = 'calls.call.push_notification'
        self.bus_publisher.publish(bus_event, headers={'user_uuid:{uuid}'.format(uuid=user_uuid): True})
