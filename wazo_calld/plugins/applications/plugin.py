# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_auth_client import Client as AuthClient
from wazo_confd_client import Client as ConfdClient
from xivo_amid_client import Client as AmidClient

from .caches import ConfdApplicationsCache
from .notifier import ApplicationNotifier
from .resources import (
    ApplicationCallAnswer,
    ApplicationCallHoldStartList,
    ApplicationCallHoldStopList,
    ApplicationCallItem,
    ApplicationCallList,
    ApplicationCallMohStartList,
    ApplicationCallMohStopList,
    ApplicationCallMuteStartList,
    ApplicationCallMuteStopList,
    ApplicationCallPlaybackList,
    ApplicationCallSnoopList,
    ApplicationItem,
    ApplicationNodeCallItem,
    ApplicationNodeCallList,
    ApplicationNodeCallUserList,
    ApplicationNodeItem,
    ApplicationNodeList,
    ApplicationPlaybackItem,
    ApplicationSnoopItem,
    ApplicationSnoopList,
)
from .services import ApplicationService
from .stasis import ApplicationStasis


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        config = dependencies['config']
        bus_consumer = dependencies['bus_consumer']
        bus_publisher = dependencies['bus_publisher']
        config = dependencies['config']
        token_changed_subscribe = dependencies['token_changed_subscribe']
        next_token_changed_subscribe = dependencies['next_token_changed_subscribe']

        auth_client = AuthClient(**config['auth'])
        confd_client = ConfdClient(**config['confd'])
        amid_client = AmidClient(**config['amid'])

        token_changed_subscribe(amid_client.set_token)
        token_changed_subscribe(auth_client.set_token)
        token_changed_subscribe(confd_client.set_token)

        confd_apps_cache = ConfdApplicationsCache(confd_client)
        confd_apps_cache.subscribe(bus_consumer)

        notifier = ApplicationNotifier(bus_publisher)
        service = ApplicationService(
            ari.client,
            confd_client,
            amid_client,
            notifier,
            confd_apps_cache,
        )

        stasis = ApplicationStasis(ari, confd_client, service, notifier, confd_apps_cache)
        next_token_changed_subscribe(stasis.initialize)

        api.add_resource(
            ApplicationItem,
            '/applications/<uuid:application_uuid>',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationCallList,
            '/applications/<uuid:application_uuid>/calls',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationCallItem,
            '/applications/<uuid:application_uuid>/calls/<call_id>',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationCallHoldStartList,
            '/applications/<uuid:application_uuid>/calls/<call_id>/hold/start',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationCallHoldStopList,
            '/applications/<uuid:application_uuid>/calls/<call_id>/hold/stop',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationCallMohStopList,
            '/applications/<uuid:application_uuid>/calls/<call_id>/moh/stop',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationCallMohStartList,
            '/applications/<uuid:application_uuid>/calls/<call_id>/moh/<uuid:moh_uuid>/start',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationCallMuteStartList,
            '/applications/<uuid:application_uuid>/calls/<call_id>/mute/start',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationCallMuteStopList,
            '/applications/<uuid:application_uuid>/calls/<call_id>/mute/stop',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationCallPlaybackList,
            '/applications/<uuid:application_uuid>/calls/<call_id>/playbacks',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationCallSnoopList,
            '/applications/<uuid:application_uuid>/calls/<call_id>/snoops',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationCallAnswer,
            '/applications/<uuid:application_uuid>/calls/<call_id>/answer',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationNodeList,
            '/applications/<uuid:application_uuid>/nodes',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationNodeItem,
            '/applications/<uuid:application_uuid>/nodes/<uuid:node_uuid>',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationNodeCallList,
            '/applications/<uuid:application_uuid>/nodes/<uuid:node_uuid>/calls',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationNodeCallUserList,
            '/applications/<uuid:application_uuid>/nodes/<uuid:node_uuid>/calls/user',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationNodeCallItem,
            '/applications/<uuid:application_uuid>/nodes/<uuid:node_uuid>/calls/<call_id>',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationPlaybackItem,
            '/applications/<uuid:application_uuid>/playbacks/<uuid:playback_uuid>',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationSnoopList,
            '/applications/<uuid:application_uuid>/snoops',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationSnoopItem,
            '/applications/<uuid:application_uuid>/snoops/<uuid:snoop_uuid>',
            resource_class_args=[service],
        )
