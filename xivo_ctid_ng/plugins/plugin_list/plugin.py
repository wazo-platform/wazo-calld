# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+


from .resource import PluginList


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        api.add_resource(PluginList,
                         '/plugins',
                         resource_class_kwargs={'enabled_plugins': dependencies['config']['enabled_plugins']})
