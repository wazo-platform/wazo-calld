# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from .models import (
    make_call_from_channel,
    make_node_from_bridge_event,
)

logger = logging.getLogger(__name__)


class AppNameHelper(object):

    PREFIX = 'wazo-app-'

    @staticmethod
    def to_uuid(name):
        if not name or not name.startswith(AppNameHelper.PREFIX):
            return
        return name[len(AppNameHelper.PREFIX):]

    @staticmethod
    def to_name(uuid):
        return '{}{}'.format(AppNameHelper.PREFIX, uuid)


class ApplicationStasis(object):

    def __init__(self, ari, confd, service, notifier):
        self._ari = ari.client
        self._core_ari = ari
        self._confd = confd
        self._service = service
        self._notifier = notifier
        self._apps_config = {}
        self._asterisk_started = False
        self._asterisk_stopped = False

    def channel_update_bridge(self, channel, event):
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid:
            return

        node = make_node_from_bridge_event(event.get('bridge'))
        self._notifier.node_updated(application_uuid, node)

        call = make_call_from_channel(channel, self._ari)
        self._notifier.call_updated(application_uuid, call)

    def initialize(self, token):
        self._confd.wait_until_ready()
        applications = self._confd.applications.list(recurse=True)['items']
        self._apps_config = {app['uuid']: app for app in applications}
        self._register_applications()
        self._subscribe()
        self._create_destinations()
        logger.debug('Stasis applications initialized')

    def stasis_start(self, event_objects, event):
        args = event.get('args', [])
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid or len(args) < 1:
            return

        command = args[0]
        if command == 'incoming':
            self._stasis_start_incoming(application_uuid, event_objects, event)
        elif command == 'originate':
            node_uuid = args[1] if len(args) > 1 else None
            self._stasis_start_originate(application_uuid, node_uuid, event_objects, event)

    def _subscribe(self):
        self._ari.on_channel_event('StasisStart', self.stasis_start)
        self._ari.on_channel_event('ChannelEnteredBridge', self.channel_update_bridge)
        self._ari.on_channel_event('ChannelLeftBridge', self.channel_update_bridge)

        for application in self._apps_config.values():
            app_uuid = application['uuid']
            self._ari.on_application_deregistered(AppNameHelper.to_name(app_uuid), self._on_stop)
            self._ari.on_application_registered(AppNameHelper.to_name(app_uuid), self._on_start)

    def _create_destinations(self):
        for application in self._apps_config.values():
            logger.critical(application)
            if application['destination'] == 'node':
                self._service.create_destination_node(application)

    def _stasis_start_incoming(self, application_uuid, event_objects, event):
        channel = event_objects['channel']
        logger.debug('new incoming call %s', channel.id)
        self._service.channel_answer(application_uuid, channel)
        application = self._apps_config[application_uuid]
        if application['destination'] == 'node':
            self._service.join_destination_node(channel.id, application)

    def _stasis_start_originate(self, application_uuid, node_uuid, event_objects, event):
        channel = event_objects['channel']
        self._service.originate_answered(application_uuid, channel)
        if node_uuid:
            self._service.join_node(application_uuid, node_uuid, [channel.id])

    def _register_applications(self):
        configured_apps = set([AppNameHelper.to_name(uuid) for uuid in self._apps_config])
        if not configured_apps:
            return

        current_apps = set([app['name'] for app in self._ari.applications.list()])
        missing_apps = configured_apps - current_apps

        if not missing_apps:
            return

        for app_name in missing_apps:
            self._core_ari.register_application(app_name)

        self._core_ari.reload()

    def _on_start(self):
        if self._asterisk_started:
            return

        logger.info('Restarting Asterisk applications')
        self._asterisk_started = True
        self._asterisk_stopped = False
        self._create_destinations()

    def _on_stop(self):
        if self._asterisk_stopped:
            return

        logger.info('Asterisk stop detected')
        self._asterisk_started = False
        self._asterisk_stopped = True
