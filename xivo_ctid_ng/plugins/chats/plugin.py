# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_auth_client import Client as AuthClient

from .contexts import ChatsContexts
from .mongooseim import Client as MongooseIMClient
from .resources import ChatsResource, UserChatsResource
from .services import ChatsService


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']

        auth_client = AuthClient(**config['auth'])
        mongooseim_client = MongooseIMClient(**config['mongooseim'])

        chats_service = ChatsService(config['uuid'], mongooseim_client, ChatsContexts, bus_publisher)

        api.add_resource(ChatsResource, '/chats', resource_class_args=[chats_service])
        api.add_resource(UserChatsResource, '/users/me/chats', resource_class_args=[auth_client, chats_service])
