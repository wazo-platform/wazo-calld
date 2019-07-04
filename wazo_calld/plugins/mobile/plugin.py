# -*- coding: utf-8 -*-
# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from .bus_consume import PushNotificationBusEventHandler


class Plugin(object):

    def load(self, dependencies):
        bus_consumer = dependencies['bus_consumer']
        bus_publisher = dependencies['bus_publisher']

        push_notification_bus_event_handler = PushNotificationBusEventHandler(bus_publisher)
        push_notification_bus_event_handler.subscribe(bus_consumer)
