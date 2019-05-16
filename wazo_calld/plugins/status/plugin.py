# Copyright 2016-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from .resources import StatusResource


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        status_aggregator = dependencies['status_aggregator']

        api.add_resource(StatusResource, '/status', resource_class_args=[status_aggregator])
