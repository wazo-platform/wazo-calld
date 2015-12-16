# -*- coding: UTF-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+


from .resources import SwaggerResource


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        SwaggerResource.add_resource(api)
