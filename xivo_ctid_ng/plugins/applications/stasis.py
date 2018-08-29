# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
import time
from requests.exceptions import (
    ConnectionError,
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
        self._ari = ari
        self._confd = confd
        self._service = service
        self._notifier = notifier
        self._apps_config = []
        self._asterisk_started = False
        self._asterisk_stopped = False

    def initialize_destination(self, token):
        self._create_destinations()
        self._wait_for_confd()
        logger.critical(self._confd.applications.list())
        self._apps_config = {app['uuid']: app for app in self._confd.applications.list()['items']}
        self.subscribe(self._apps_config.values())
        logger.debug('Stasis applications initialized')

    def stasis_start(self, event_objects, event):
        logger.debug('######## %s ########', event.get('application'))
        args = event.get('args', [])
        application_uuid = AppNameHelper.to_uuid(event.get('application'))
        if not application_uuid or len(args) < 1:
            return

        if args[0] == 'incoming':
            self._stasis_start_incoming(application_uuid, event_objects, event)

    def subscribe(self, applications):
        logger.debug('######## subscribing ########')
        self._ari.on_channel_event('StasisStart', self.stasis_start)

    def _stasis_start_incoming(self, application_uuid, event_objects, event):
        channel = event_objects['channel']
        logger.debug('new incoming call %s', channel.id)
        self._service.channel_answer(application_uuid, channel)
        self._service.join_destination_node(channel.id, self._apps_config[application_uuid])

    def _create_destinations(self):
        for application in self._apps_config:
            if application['destination'] == 'node':
                self._service.create_destination_node(application)

    def _wait_for_confd(self):
        retry = 20
        for n in xrange(retry):
            try:
                self._confd.infos()
                return
            except ConnectionError:
                if n < retry - 1:
                    time.sleep(0.2)

            raise Exception('Failed to connect to xivo-confd')
