# -*- coding: UTF-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+


from .resources import CallResource
from .resources import CallsResource
from .resources import ConnectCallToUserResource
from .services import CallsService


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        token_changed_subscribe = dependencies['token_changed_subscribe']
        config = dependencies['config']

        calls_service = CallsService(ari_config=config['ari']['connection'], confd_config=config['confd'])
        token_changed_subscribe(calls_service.set_confd_token)

        api.add_resource(CallsResource, '/calls', resource_class_args=[calls_service])
        api.add_resource(CallResource, '/calls/<call_id>', resource_class_args=[calls_service])
        api.add_resource(ConnectCallToUserResource, '/calls/<call_id>/user/<user_id>', resource_class_args=[calls_service])
