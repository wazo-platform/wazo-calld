# -*- coding: UTF-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_auth_client import Client as AuthClient
from xivo_ctid_ng.plugins.chats.contexts import ChatsContexts
from .resources import (
    CheckPasswordResource,
    MessageCallbackResource,
    PresenceCallbackResource,
    UserExistsResource,
)
from .services import MessageCallbackService, PresenceCallbackService


class Plugin:

    def load(self, dependencies):
        adapter_api = dependencies['adapter_api']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']

        auth_client = AuthClient(**config['auth'])

        message_callback_service = MessageCallbackService(bus_publisher, config['uuid'], ChatsContexts)
        adapter_api.add_resource(MessageCallbackResource,
                                 '/mongooseim/message_callback',
                                 resource_class_args=[message_callback_service])

        presence_callback_service = PresenceCallbackService(bus_publisher, config['uuid'])
        adapter_api.add_resource(PresenceCallbackResource,
                                 '/mongooseim/presence_callback',
                                 resource_class_args=[presence_callback_service])

        adapter_api.add_resource(CheckPasswordResource,
                                 '/mongooseim/authentication/check_password', resource_class_args=[auth_client])

        adapter_api.add_resource(UserExistsResource,
                                 '/mongooseim/authentication/user_exists')
