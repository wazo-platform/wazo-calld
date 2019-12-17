# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_confd_client import Client as ConfdClient

from wazo_calld.ari_ import DEFAULT_APPLICATION_NAME

from .confd_client_cache import (
    ConfdClientGetIDCacheDecorator,
    ConfdClientGetUUIDCacheDecorator,
    ConfdClientUserLineGetCacheDecorator,
)
from .notifier import SwitchboardsNotifier
from .resources import (
    SwitchboardCallHeldAnswerResource,
    SwitchboardCallHeldResource,
    SwitchboardCallQueuedAnswerResource,
    SwitchboardCallsHeldResource,
    SwitchboardCallsQueuedResource,
)
from .services import SwitchboardsService
from .stasis import SwitchboardsStasis


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        bus_publisher = dependencies['bus_publisher']
        bus_consumer = dependencies['bus_consumer']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']

        confd_client = ConfdClient(**config['confd'])
        switchboard_get_cache = ConfdClientGetUUIDCacheDecorator(confd_client.switchboards.get, resource_name='switchboard')
        confd_client.switchboards.get = switchboard_get_cache
        line_get_cache = ConfdClientGetIDCacheDecorator(confd_client.lines.get, resource_name='line')
        confd_client.lines.get = line_get_cache
        user_line_get_cache = ConfdClientUserLineGetCacheDecorator(confd_client.users.get, resource_name='user')
        confd_client.users.get = user_line_get_cache

        token_changed_subscribe(confd_client.set_token)

        switchboards_notifier = SwitchboardsNotifier(bus_publisher)
        switchboards_service = SwitchboardsService(ari.client, confd_client, switchboards_notifier)

        ari.register_application(DEFAULT_APPLICATION_NAME)
        switchboards_stasis = SwitchboardsStasis(ari.client, confd_client, switchboards_notifier, switchboards_service)
        switchboards_stasis.subscribe()
        switchboard_get_cache.subscribe(bus_consumer, events=['switchboard_edited', 'switchboard_deleted'])
        # line-endpoint association emits line_edited too
        line_get_cache.subscribe(bus_consumer, events=['line_edited', 'line_deleted'])
        user_line_get_cache.subscribe(bus_consumer)

        api.add_resource(
            SwitchboardCallsQueuedResource,
            '/switchboards/<switchboard_uuid>/calls/queued',
            resource_class_args=[switchboards_service],
        )
        api.add_resource(
            SwitchboardCallQueuedAnswerResource,
            '/switchboards/<switchboard_uuid>/calls/queued/<call_id>/answer',
            resource_class_args=[switchboards_service],
        )
        api.add_resource(
            SwitchboardCallsHeldResource,
            '/switchboards/<switchboard_uuid>/calls/held',
            resource_class_args=[switchboards_service],
        )
        api.add_resource(
            SwitchboardCallHeldResource,
            '/switchboards/<switchboard_uuid>/calls/held/<call_id>',
            resource_class_args=[switchboards_service],
        )
        api.add_resource(
            SwitchboardCallHeldAnswerResource,
            '/switchboards/<switchboard_uuid>/calls/held/<call_id>/answer',
            resource_class_args=[switchboards_service],
        )
