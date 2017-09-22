# -*- coding: UTF-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.plugins.chats.contexts import ChatsContexts
from .resources import MessageCallbackResource, CheckPasswordResource, UserExistsResource
from .services import MessageCallbackService


class Plugin(object):

    def load(self, dependencies):
        adapter_api = dependencies['adapter_api']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']

        message_callback_service = MessageCallbackService(bus_publisher, config['uuid'], ChatsContexts)
        adapter_api.add_resource(MessageCallbackResource,
                                 '/mongooseim/message_callback',
                                 resource_class_args=[message_callback_service])

        adapter_api.add_resource(CheckPasswordResource,
                                 '/mongooseim/authentication/check_password')

        adapter_api.add_resource(UserExistsResource,
                                 '/mongooseim/authentication/user_exists')
