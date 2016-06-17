# -*- coding: UTF-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_auth_client import Client as AuthClient

from .resources import ChatsResource, UserChatsResource
from .services import ChatsService


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']

        auth_client = AuthClient(**config['auth'])

        chats_service = ChatsService(bus_publisher, config['uuid'])

        api.add_resource(ChatsResource, '/chats', resource_class_args=[chats_service])
        api.add_resource(UserChatsResource, '/users/me/chats', resource_class_args=[auth_client, chats_service])
