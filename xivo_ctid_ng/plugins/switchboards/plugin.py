# -*- coding: UTF-8 -*-
# Copyright 2017 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_confd_client import Client as ConfdClient

from .notifier import SwitchboardsNotifier
from .resources import SwitchboardCallsQueuedResource
from .services import SwitchboardsService
from .stasis import SwitchboardsStasis


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']

        confd_client = ConfdClient(**config['confd'])

        switchboards_notifier = SwitchboardsNotifier(bus_publisher)
        switchboards_service = SwitchboardsService(ari.client, confd_client, switchboards_notifier)

        switchboards_stasis = SwitchboardsStasis(ari.client, switchboards_service)
        switchboards_stasis.subscribe()

        api.add_resource(SwitchboardCallsQueuedResource, '/switchboards/<switchboard_uuid>/calls/queued', resource_class_args=[switchboards_service])
