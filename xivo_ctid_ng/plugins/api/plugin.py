# -*- coding: UTF-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+


from .resources import SwaggerResource


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        api.add_resource(SwaggerResource, '/api/api.yml')
