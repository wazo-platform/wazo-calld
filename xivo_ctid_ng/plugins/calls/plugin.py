# -*- coding: UTF-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+


from .resources import CallResource, CallsResource
from .services import CallsService


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        calls_service = CallsService(ari_config=dependencies['config']['ari']['connection'],
                                     confd_config=dependencies['config']['confd'])
        api.add_resource(CallsResource, '/calls', resource_class_args=[calls_service])
        api.add_resource(CallResource, '/calls/<call_id>', resource_class_args=[calls_service])
