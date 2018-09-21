# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_amid_client import Client as AmidClient
from xivo_auth_client import Client as AuthClient
from xivo_confd_client import Client as ConfdClient

from .notifier import ApplicationNotifier
from .resources import (
    ApplicationCallItem,
    ApplicationCallList,
    ApplicationCallMohStopList,
    ApplicationCallMohStartList,
    ApplicationCallPlaybackList,
    ApplicationPlaybackItem,
    ApplicationItem,
    ApplicationNodeCallItem,
    ApplicationNodeCallList,
    ApplicationNodeItem,
    ApplicationNodeList,
)
from .services import ApplicationService
from .stasis import ApplicationStasis


class Plugin(object):

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        config = dependencies['config']
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

        notifier = ApplicationNotifier(bus_publisher)
        service = ApplicationService(ari.client, confd_client, amid_client, notifier)

        stasis = ApplicationStasis(ari, confd_client, service, notifier)
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
            ApplicationCallPlaybackList,
            '/applications/<uuid:application_uuid>/calls/<call_id>/playbacks',
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
            ApplicationNodeCallItem,
            '/applications/<uuid:application_uuid>/nodes/<uuid:node_uuid>/calls/<call_id>',
            resource_class_args=[service],
        )
        api.add_resource(
            ApplicationPlaybackItem,
            '/applications/<uuid:application_uuid>/playbacks/<uuid:playback_uuid>',
            resource_class_args=[service],
        )
