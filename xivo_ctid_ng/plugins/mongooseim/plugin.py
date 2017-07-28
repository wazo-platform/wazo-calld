# -*- coding: UTF-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from .resources import MessageCallbackResource
from .services import MessageCallbackService


class Plugin(object):

    def load(self, dependencies):
        api_adapter = dependencies['api_adapter']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']

        message_callback_service = MessageCallbackService(bus_publisher, config['uuid'])
        api_adapter.add_resource(MessageCallbackResource,
                                 '/mongooseim/message_callback',
                                 resource_class_args=[message_callback_service])
