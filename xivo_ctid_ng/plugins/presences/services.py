# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_bus.resources.cti.event import UserStatusUpdateEvent

import requests

from .exceptions import XiVOCtidUnreachable


class PresencesService(object):

    def __init__(self, bus_publisher, ctid_client, ctid_config):
        self._bus_publisher = bus_publisher
        self._ctid_client = ctid_client
        self._ctid_config = ctid_config

    def get_presence(self, user_uuid):
        try:
            return self._ctid_client.users.get(user_uuid)
        except requests.RequestException as e:
            raise XiVOCtidUnreachable(self._ctid_config, e)

        return '', 404

    def update_presence(self, user_uuid, request_body):
        bus_event = UserStatusUpdateEvent(user_uuid, request_body['presence'])
        self._bus_publisher.publish(bus_event)
