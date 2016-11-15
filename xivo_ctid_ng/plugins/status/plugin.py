# -*- coding: UTF-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from .resources import StatusResource


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        status_aggregator = dependencies['status_aggregator']

        api.add_resource(StatusResource, '/status', resource_class_args=[status_aggregator])
