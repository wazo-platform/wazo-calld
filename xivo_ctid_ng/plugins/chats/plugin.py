# -*- coding: UTF-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_auth_client import Client as AuthClient

from .contexts import ChatsContexts
from .resources import ChatsResource, UserChatsResource
from .services import ChatsService


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        config = dependencies['config']

        auth_client = AuthClient(**config['auth'])

        chats_service = ChatsService(config['uuid'], config['mongooseim'], ChatsContexts)

        api.add_resource(ChatsResource, '/chats', resource_class_args=[chats_service])
        api.add_resource(UserChatsResource, '/users/me/chats', resource_class_args=[auth_client, chats_service])
