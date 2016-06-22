# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_bus.resources.cti.event import UserStatusUpdateEvent


class PresencesService(object):

    def __init__(self, bus_publisher):
        self._bus_publisher = bus_publisher

    def get_presence(self, user_uuid):
        presence = { "id": user_uuid,
                     "origin_uuid": "xivo-uuid",
                     "presence": "available"
                   }
        return presence

    def update_presence(self, user_uuid, request_body):
        bus_event = UserStatusUpdateEvent(user_uuid, request_body['status_name'])
        self._bus_publisher.publish(bus_event)
