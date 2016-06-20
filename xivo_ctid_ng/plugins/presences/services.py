# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_bus.resources.cti.event import UserStatusUpdateEvent


class PresencesService(object):

    def __init__(self, bus_publisher):
        self._bus_publisher = bus_publisher

    def update_presence(self, request_body, user_uuid=None):
        bus_event = UserStatusUpdateEvent(self._build_user_uuid(request_body, user_uuid),
                                          request_body['status_name'])
        self._bus_publisher.publish(bus_event)

    def _build_user_uuid(self, request_body, token_user_uuid):
        user_uuid = token_user_uuid or str(request_body['user_uuid'])
        return user_uuid
