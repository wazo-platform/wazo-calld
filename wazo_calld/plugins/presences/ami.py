# -*- coding: utf-8 -*-
# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo.asterisk.protocol_interface import protocol_interface_from_device
from xivo_bus.resources.cti.event import EndpointStatusUpdateEvent

logger = logging.getLogger(__name__)


class AMIEventHandler(object):

    _DEVICE_STATE_MAP = {
        'UNKNOWN': '4',
        'NOT_INUSE': '0',
        'INUSE': '1',
        'BUSY': '2',
        'INVALID': '4',
        'UNAVAILABLE': '4',
        'RINGING': '8',
        'RINGINUSE': '9',
        'ONHOLD': '16',
    }

    def __init__(self, bus_publisher, confd):
        self._bus_publisher = bus_publisher
        self._confd = confd

    def subscribe(self, bus_consumer):
        bus_consumer.on_ami_event('DeviceStateChange', self.on_device_state_change)

    def on_device_state_change(self, event):
        device = event['Device']
        state_name = event['State']

        result = protocol_interface_from_device(device.lower())
        if not result:
            return None
        protocol, interface = result
        lines = self._confd.lines.list(protocol=protocol, name=interface)['items']
        if not lines:
            return
        line = lines[0]

        users = self._confd.lines.relations(line['id']).list_users()['items']
        users = [user for user in users if user['main_user'] is True]
        user_id = users[0]['user_id'] if users else None
        if not user_id:
            user = None
        else:
            user = self._confd.users.get(user_id)

        state = self._DEVICE_STATE_MAP[state_name]
        bus_event = EndpointStatusUpdateEvent(line['id'], state)
        headers = {}
        if user:
            headers['user_uuid:{user[uuid]}'.format(user=user)] = True
        self._bus_publisher.publish(bus_event, headers=headers)
