# Copyright 2018-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from wazo_calld.plugin_helpers.ari_ import set_channel_var_sync, Channel as _ChannelHelper

from .exceptions import NoSuchSnoop
from .models import CallFormatter, make_node_from_bridge, make_node_from_bridge_event

logger = logging.getLogger(__name__)


class AppNameHelper:
    PREFIX = 'wazo-app-'

    @staticmethod
    def to_uuid(name):
        if not name or not name.startswith(AppNameHelper.PREFIX):
            return
        return name[len(AppNameHelper.PREFIX) :]

    @staticmethod
    def to_name(uuid):
        return f'{AppNameHelper.PREFIX}{uuid}'


class ApplicationStasis:
    def __init__(self, ari, service, notifier, confd_apps, moh):
        self._ari = ari.client
        self._confd_apps = confd_apps
        self._moh = moh
        self._core_ari = ari
        self._service = service
        self._notifier = notifier

    def channel_dtmf_received(self, channel, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return
        application = self._service.get_application(application_uuid)
        channel = _ChannelHelper(channel.id, self._ari)
        conversation_id = channel.conversation_id()

        self._notifier.dtmf_received(
            application, channel.id, conversation_id, event['digit']
        )

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
                self._notifier.snoop_updated(application, snoop)
            except NoSuchSnoop:
                self._notifier.snoop_deleted(application, snoop_uuid)

        self._channel_update_bridge(application_uuid, channel, event)

    def _channel_update_bridge(self, application_uuid, channel, event):
        application = self._service.get_application(application_uuid)

        node = make_node_from_bridge_event(event.get('bridge'))
        self._notifier.node_updated(application, node)

        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel)
        self._notifier.call_updated(application, call)

    def initialize(self):
        applications = self._confd_apps.list()
        self._subscribe(applications)
        self._register_applications(applications)
        logger.debug('Stasis applications initialized')

    def add_ari_application(self, application):
        app_name = AppNameHelper.to_name(application['uuid'])
        self._ari.on_application_registered(app_name, self._on_application_registered)
        self._core_ari.register_application(app_name)
        logger.debug('Stasis application added')

    def remove_ari_application(self, application):
        app_name = AppNameHelper.to_name(application['uuid'])

        # Should be implemented in ari-py
        self._ari._app_registered_callbacks.pop(app_name, None)
        self._ari._app_deregistered_callbacks.pop(app_name, None)

        self._core_ari.deregister_application(app_name)
        logger.debug('Stasis application removed')

    def stasis_start(self, event_objects, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        if not event['args']:
            return self._stasis_start_user_outgoing(
                application_uuid, event_objects, event
            )

        command, *command_args = event['args']
        if command == 'incoming':
            self._stasis_start_incoming(application_uuid, event_objects, event)
        elif command == 'originate':
            node_uuid = command_args[0] if command_args else None
            self._stasis_start_originate(
                application_uuid, node_uuid, event_objects, event
            )

    def stasis_end(self, channel, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        application = self._service.get_application(application_uuid)
        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel)
        self._notifier.call_deleted(application, call)

    def bridge_destroyed(self, bridge, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return
        application = self._service.get_application(application_uuid)

        node = make_node_from_bridge(bridge)
        self._notifier.node_deleted(application, node)

    def channel_moh_started(self, channel, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        application = self._service.get_application(application_uuid)

        moh = self._moh.find_by_name(event['moh_class'])
        if moh:
            set_channel_var_sync(channel, 'WAZO_MOH_UUID', str(moh['uuid']))

        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel)
        self._notifier.call_updated(application, call)

    def channel_moh_stopped(self, channel, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        application = self._service.get_application(application_uuid)

        set_channel_var_sync(channel, 'WAZO_MOH_UUID', '')
        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel)
        self._notifier.call_updated(application, call)

    def channel_state_change(self, channel, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        application = self._service.get_application(application_uuid)

        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel)

        if channel.json['state'] == 'Up':
            self._notifier.call_answered(application, call)

    def channel_variable_set(self, channel, event):
        if event['variable'] == 'WAZO_CALL_PROGRESS':
            application_uuid = AppNameHelper.to_uuid(event.get('application'))
            if not application_uuid:
                return

            application = self._service.get_application(application_uuid)

            formatter = CallFormatter(application, self._ari)
            call = formatter.from_channel(channel)

            if event['value'] == '1':
                self._notifier.call_progress_started(application, call)
            else:
                self._notifier.call_progress_stopped(application, call)

    def playback_finished(self, playback, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return
        application = self._service.get_application(application_uuid)

        self._notifier.playback_deleted(application, playback.json)

    def playback_started(self, playback, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return
        application = self._service.get_application(application_uuid)

        self._notifier.playback_created(application, playback.json)

    def _subscribe(self, applications):
        self._ari.on_playback_event('PlaybackStarted', self.playback_started)
        self._ari.on_playback_event('PlaybackFinished', self.playback_finished)
        self._ari.on_channel_event('ChannelDtmfReceived', self.channel_dtmf_received)
        self._ari.on_channel_event('ChannelMohStart', self.channel_moh_started)
        self._ari.on_channel_event('ChannelMohStop', self.channel_moh_stopped)
        self._ari.on_channel_event('ChannelVarset', self.channel_variable_set)
        self._ari.on_channel_event('StasisStart', self.stasis_start)
        self._ari.on_channel_event('StasisEnd', self.stasis_end)
        self._ari.on_channel_event('ChannelEnteredBridge', self.channel_entered_bridge)
        self._ari.on_channel_event('ChannelLeftBridge', self.channel_left_bridge)
        self._ari.on_channel_event('ChannelStateChange', self.channel_state_change)
        self._ari.on_bridge_event('BridgeDestroyed', self.bridge_destroyed)

        for application in applications:
            app_uuid = application['uuid']
            app_name = AppNameHelper.to_name(app_uuid)
            self._ari.on_application_registered(
                app_name, self._on_application_registered
            )
            self._core_ari.register_application(app_name)

    def _create_destinations(self, applications):
        logger.info('Creating destination nodes')
        for application in applications:
            if application['destination'] == 'node':
                self._service.create_destination_node(application)

    def _stasis_start_incoming(self, application_uuid, event_objects, event):
        channel = event_objects['channel']
        logger.debug('new incoming call %s', channel.id)

        application = self._service.get_application(application_uuid)
        variables = self._service.get_channel_variables(channel)
        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel, variables=variables)
        self._notifier.call_entered(application, call)

        confd_application = self._confd_apps.get(application_uuid)
        if confd_application['destination'] == 'node':
            self._service.join_destination_node(channel, confd_application)

    def _stasis_start_user_outgoing(self, application_uuid, event_objects, event):
        channel = event_objects['channel']
        logger.debug('new user outgoing call %s', channel.id)
        application = self._service.get_application(application_uuid)
        self._service.start_user_outgoing_call(application, channel)

    def _stasis_start_originate(
        self, application_uuid, node_uuid, event_objects, event
    ):
        channel = event_objects['channel']
        application = self._service.get_application(application_uuid)
        self._service.originate_answered(application, channel)
        if node_uuid:
            self._service.join_node(application_uuid, node_uuid, [channel.id])

    def _register_applications(self, applications):
        apps_name = {AppNameHelper.to_name(app['uuid']) for app in applications}
        for app_name in apps_name:
            self._core_ari.register_application(app_name)

    def _on_application_registered(self):
        applications = self._confd_apps.list()
        self._create_destinations(applications)
