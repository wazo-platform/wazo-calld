# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

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

    def initialize(self, token):
        self._confd.wait()
        self._apps_config = {app['uuid']: app for app in self._confd.applications.list()['items']}
        self._register_applications()
        self.subscribe(self._apps_config.values())
        logger.debug('Stasis applications initialized')

    def stasis_start(self, event_objects, event):
        args = event.get('args', [])
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid or len(args) < 1:
            return

        if args[0] == 'incoming':
            self._stasis_start_incoming(application_uuid, event_objects, event)

    def subscribe(self, applications):
        self._ari.on_channel_event('StasisStart', self.stasis_start)

    def _stasis_start_incoming(self, application_uuid, event_objects, event):
        channel = event_objects['channel']
        logger.debug('new incoming call %s', channel.id)
        self._service.channel_answer(application_uuid, channel)
        self._service.join_destination_node(channel.id, self._apps_config[application_uuid])

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
