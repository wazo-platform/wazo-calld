# Copyright 2015-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_auth_client import Client as AuthClient
from wazo_confd_client import Client as ConfdClient
from wazo_amid_client import Client as AmidClient
from xivo.pubsub import CallbackCollector
from wazo_calld.phoned import PhonedClient

from .bus_consume import CallsBusEventHandler
from .notifier import CallNotifier
from .dial_echo import DialEchoManager
from .http import (
    CallResource,
    CallMuteStartResource,
    CallMuteStopResource,
    CallDtmfResource,
    CallHoldResource,
    CallUnholdResource,
    CallsResource,
    CallAnswerResource,
    ConnectCallToUserResource,
    MyCallResource,
    MyCallsResource,
    MyCallMuteStartResource,
    MyCallMuteStopResource,
    MyCallDtmfResource,
    MyCallHoldResource,
    MyCallUnholdResource,
    MyCallAnswerResource,
)
from .services import CallsService
from .stasis import CallsStasis


class Plugin:

    def load(self, dependencies):
        api = dependencies['api']
        ari = dependencies['ari']
        bus_consumer = dependencies['bus_consumer']
        bus_publisher = dependencies['bus_publisher']
        collectd = dependencies['collectd']
        token_changed_subscribe = dependencies['token_changed_subscribe']
        config = dependencies['config']

        amid_client = AmidClient(**config['amid'])
        token_changed_subscribe(amid_client.set_token)

        auth_client = AuthClient(**config['auth'])
        confd_client = ConfdClient(**config['confd'])
        phoned_client = PhonedClient(**config['phoned'])

        token_changed_subscribe(confd_client.set_token)
        token_changed_subscribe(phoned_client.set_token)

        dial_echo_manager = DialEchoManager()

        notifier = CallNotifier(bus_publisher)
        calls_service = CallsService(amid_client, config['ari']['connection'], ari.client, confd_client, dial_echo_manager, phoned_client, notifier)

        calls_stasis = CallsStasis(ari, collectd, bus_publisher, calls_service, config['uuid'], amid_client)

        startup_callback_collector = CallbackCollector()
        ari.client_initialized_subscribe(startup_callback_collector.new_source())
        startup_callback_collector.subscribe(calls_stasis.initialize)

        calls_bus_event_handler = CallsBusEventHandler(
            amid_client,
            ari.client,
            collectd,
            bus_publisher,
            calls_service,
            config['uuid'],
            dial_echo_manager,
            notifier,
        )
        calls_bus_event_handler.subscribe(bus_consumer)

        api.add_resource(CallsResource, '/calls', resource_class_args=[calls_service])
        api.add_resource(MyCallsResource, '/users/me/calls', resource_class_args=[auth_client, calls_service])
        api.add_resource(CallResource, '/calls/<call_id>', resource_class_args=[calls_service])
        api.add_resource(CallMuteStartResource, '/calls/<call_id>/mute/start', resource_class_args=[calls_service])
        api.add_resource(CallMuteStopResource, '/calls/<call_id>/mute/stop', resource_class_args=[calls_service])
        api.add_resource(CallDtmfResource, '/calls/<call_id>/dtmf', resource_class_args=[calls_service])
        api.add_resource(CallHoldResource, '/calls/<call_id>/hold/start', resource_class_args=[calls_service])
        api.add_resource(CallUnholdResource, '/calls/<call_id>/hold/stop', resource_class_args=[calls_service])
        api.add_resource(CallAnswerResource, '/calls/<call_id>/answer', resource_class_args=[calls_service])
        api.add_resource(MyCallResource, '/users/me/calls/<call_id>', resource_class_args=[auth_client, calls_service])
        api.add_resource(MyCallMuteStartResource, '/users/me/calls/<call_id>/mute/start', resource_class_args=[auth_client, calls_service])
        api.add_resource(MyCallMuteStopResource, '/users/me/calls/<call_id>/mute/stop', resource_class_args=[auth_client, calls_service])
        api.add_resource(MyCallDtmfResource, '/users/me/calls/<call_id>/dtmf', resource_class_args=[auth_client, calls_service])
        api.add_resource(MyCallHoldResource, '/users/me/calls/<call_id>/hold/start', resource_class_args=[auth_client, calls_service])
        api.add_resource(MyCallUnholdResource, '/users/me/calls/<call_id>/hold/stop', resource_class_args=[auth_client, calls_service])
        api.add_resource(MyCallAnswerResource, '/users/me/calls/<call_id>/answer', resource_class_args=[auth_client, calls_service])
        api.add_resource(ConnectCallToUserResource, '/calls/<call_id>/user/<user_uuid>', resource_class_args=[calls_service])
