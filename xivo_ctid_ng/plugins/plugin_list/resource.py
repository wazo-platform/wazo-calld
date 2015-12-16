# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+


from flask import jsonify
from xivo_ctid_ng.core.rest_api import AuthResource


class PluginList(AuthResource):

    def __init__(self, enabled_plugins):
        self._enabled_plugins = enabled_plugins

    def get(self):
        plugins = self._enabled_plugins
        return jsonify({'items': plugins})
