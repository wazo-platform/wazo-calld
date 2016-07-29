# -*- coding: UTF-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from .resources import StatusResource
from .services import StatusService


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        bus_consumer = dependencies['bus_consumer']

        status_service = StatusService(ari, bus_consumer)

        api.add_resource(StatusResource, '/status', resource_class_args=[status_service])
