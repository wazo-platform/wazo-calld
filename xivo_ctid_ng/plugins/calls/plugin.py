# -*- coding: UTF-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+


from .resources import CallResource, CallsResource


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        api.add_resource(CallsResource, '/calls')
        api.add_resource(CallResource, '/calls/<call_id>')
