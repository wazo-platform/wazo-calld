# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from .exceptions import (
    NoSuchSnoop,
)
from .models import (
    CallFormatter,
    make_node_from_bridge,
    make_node_from_bridge_event,
)

logger = logging.getLogger(__name__)


class AppNameHelper:

    PREFIX = 'wazo-app-'

    @staticmethod
    def to_uuid(name):
        if not name or not name.startswith(AppNameHelper.PREFIX):
            return
        return name[len(AppNameHelper.PREFIX):]

    @staticmethod
    def to_name(uuid):
        return '{}{}'.format(AppNameHelper.PREFIX, uuid)


class ApplicationStasis:

    def __init__(self, ari, confd, service, notifier):
        self._ari = ari.client
        self._confd = confd
        self._core_ari = ari
        self._service = service
        self._notifier = notifier
        self._destination_created = False

    def channel_dtmf_received(self, channel, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        self._notifier.dtmf_received(application_uuid, channel.id, event['digit'])

    def channel_entered_bridge(self, channel, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        self._channel_update_bridge(application_uuid, channel, event)

    def channel_left_bridge(self, channel, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        if channel.json['name'].startswith('Snoop/'):
            application = self._service.get_application(application_uuid)
            snoop_uuid = event['bridge']['id']
            try:
                snoop = self._service.snoop_get(application, snoop_uuid)
                self._notifier.snoop_updated(application_uuid, snoop)
            except NoSuchSnoop:
                self._notifier.snoop_deleted(application_uuid, snoop_uuid)

        self._channel_update_bridge(application_uuid, channel, event)

    def _channel_update_bridge(self, application_uuid, channel, event):
        application = self._service.get_application(application_uuid)

        node = make_node_from_bridge_event(event.get('bridge'))
        self._notifier.node_updated(application_uuid, node)

        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel)
        self._notifier.call_updated(application_uuid, call)

    def initialize(self, token):
        self._confd.wait_until_ready()
        applications = self._service.list_confd_applications()
        self._subscribe(applications)
        self._register_applications(applications)
        logger.debug('Stasis applications initialized')

    def stasis_start(self, event_objects, event):
        args = event.get('args', [])
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if application_uuid and len(args) < 1:
            args = ['user']
        if not application_uuid or len(args) < 1:
            return

        command = args[0]
        if command == 'incoming':
            self._stasis_start_incoming(application_uuid, event_objects, event)
        elif command == 'originate':
            node_uuid = args[1] if len(args) > 1 else None
            self._stasis_start_originate(application_uuid, node_uuid, event_objects, event)
        elif command == 'user':
            self._stasis_start_user(application_uuid, event_objects, event)

    def stasis_end(self, channel, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        application = self._service.get_application(application_uuid)
        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel)
        self._notifier.call_deleted(application_uuid, call)

    def bridge_destroyed(self, bridge, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        node = make_node_from_bridge(bridge)
        self._notifier.node_deleted(application_uuid, node)

    def channel_moh_started(self, channel, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        application = self._service.get_application(application_uuid)

        moh = self._service.find_moh(event['moh_class'])
        if moh:
            self._service.set_channel_var_sync(channel, 'WAZO_MOH_UUID', str(moh['uuid']))

        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel)
        self._notifier.call_updated(application_uuid, call)

    def channel_moh_stopped(self, channel, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        application = self._service.get_application(application_uuid)

        self._service.set_channel_var_sync(channel, 'WAZO_MOH_UUID', '')
        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel)
        self._notifier.call_updated(application_uuid, call)

    def channel_state_change(self, channel, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        application = self._service.get_application(application_uuid)

        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel)

        if channel.json['state'] == 'Up':
            self._notifier.call_answered(application_uuid, call)

    def playback_finished(self, playback, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        self._notifier.playback_deleted(application_uuid, playback.json)

    def playback_started(self, playback, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        self._notifier.playback_created(application_uuid, playback.json)

    def _subscribe(self, applications):
        self._ari.on_playback_event('PlaybackStarted', self.playback_started)
        self._ari.on_playback_event('PlaybackFinished', self.playback_finished)
        self._ari.on_channel_event('ChannelDtmfReceived', self.channel_dtmf_received)
        self._ari.on_channel_event('ChannelMohStart', self.channel_moh_started)
        self._ari.on_channel_event('ChannelMohStop', self.channel_moh_stopped)
        self._ari.on_channel_event('StasisStart', self.stasis_start)
        self._ari.on_channel_event('StasisEnd', self.stasis_end)
        self._ari.on_channel_event('ChannelEnteredBridge', self.channel_entered_bridge)
        self._ari.on_channel_event('ChannelLeftBridge', self.channel_left_bridge)
        self._ari.on_channel_event('ChannelStateChange', self.channel_state_change)
        self._ari.on_bridge_event('BridgeDestroyed', self.bridge_destroyed)

        for application in applications:
            app_uuid = application['uuid']
            app_name = AppNameHelper.to_name(app_uuid)
            self._ari.on_application_deregistered(app_name, self._on_websocket_stop)
            self._ari.on_application_registered(app_name, self._on_websocket_start)

    def _create_destinations(self, applications):
        logger.info('Creating destination nodes')
        for application in applications:
            if application['destination'] == 'node':
                self._service.create_destination_node(application)
        self._destination_created = True

    def _stasis_start_incoming(self, application_uuid, event_objects, event):
        channel = event_objects['channel']
        logger.debug('new incoming call %s', channel.id)

        application = self._service.get_application(application_uuid)
        variables = self._service.get_channel_variables(channel)
        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel, variables=variables)
        self._notifier.call_entered(application['uuid'], call)

        confd_application = self._service.get_confd_application(application_uuid)
        if confd_application['destination'] == 'node':
            self._service.join_destination_node(channel, confd_application)

    def _stasis_start_user(self, application_uuid, event_objects, event):
        channel = event_objects['channel']
        logger.debug('new incoming call user %s', channel.id)
        application = self._service.get_application(application_uuid)
        self._service.channel_user_entered(application, channel)

    def _stasis_start_originate(self, application_uuid, node_uuid, event_objects, event):
        channel = event_objects['channel']
        application = self._service.get_application(application_uuid)
        self._service.originate_answered(application, channel)
        if node_uuid:
            self._service.join_node(application_uuid, node_uuid, [channel.id])

    def _register_applications(self, applications):
        apps_name = set([AppNameHelper.to_name(app['uuid']) for app in applications])
        for app_name in apps_name:
            self._core_ari.register_application(app_name)

        self._core_ari.reload()

    def _on_websocket_start(self):
        if self._destination_created:
            return

        applications = self._service.list_confd_applications()
        self._create_destinations(applications)

    def _on_websocket_stop(self):
        self._destination_created = False
