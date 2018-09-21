# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from requests import HTTPError
from ari.exceptions import ARINotFound
from xivo_ctid_ng.helpers import ami
from xivo_ctid_ng.exceptions import InvalidExtension
from .models import (
    make_call_from_channel,
    make_node_from_bridge,
)
from .exceptions import (
    CallAlreadyInNode,
    DeleteDestinationNode,
    NoSuchApplication,
    NoSuchCall,
    NoSuchMedia,
    NoSuchMoh,
    NoSuchNode,
    NoSuchPlayback,
)
from .stasis import AppNameHelper

logger = logging.getLogger(__name__)


class ApplicationService(object):

    def __init__(self, ari, confd, amid, notifier):
        self._ari = ari
        self._confd = confd
        self._amid = amid
        self._notifier = notifier
        self._apps_cache = None
        self._moh_cache = None

    def channel_answer(self, application_uuid, channel):
        channel.answer()
        variables = self.get_channel_variables(channel)
        call = make_call_from_channel(channel, ari=self._ari, variables=variables)
        self._notifier.call_entered(application_uuid, call)

    def create_destination_node(self, application):
        try:
            bridge = self._ari.bridges.get(bridgeId=application['uuid'])
        except ARINotFound:
            bridge_type = application['destination_options']['type']
            bridge = self._ari.bridges.createWithId(
                bridgeId=application['uuid'],
                name=application['uuid'],
                type=bridge_type,
            )
            node = make_node_from_bridge(bridge)
            self._notifier.destination_node_created(application['uuid'], node)

    def create_node_with_calls(self, application_uuid, call_ids):
        bridges = self._ari.bridges.list()
        self.validate_call_not_in_node(application_uuid, bridges, call_ids)

        bridge = self._ari.bridges.create(name=application_uuid, type='mixing')
        node = make_node_from_bridge(bridge)
        self._notifier.node_created(application_uuid, node)

        self.join_node(application_uuid, bridge.id, call_ids)
        node = make_node_from_bridge(bridge.get())
        return node

    def get_application(self, application_uuid):
        try:
            application = self._ari.applications.get(
                applicationName=AppNameHelper.to_name(application_uuid)
            )
        except ARINotFound:
            raise NoSuchApplication(application_uuid)

        node_uuid = None
        confd_app = self.get_confd_application(application_uuid)
        if confd_app['destination'] == 'node':
            node_uuid = application_uuid

        application['destination_node_uuid'] = node_uuid
        application['uuid'] = application_uuid
        return application

    def get_confd_application(self, application_uuid):
        application = self._apps_cache.get(str(application_uuid))
        if not application:
            raise NoSuchApplication(application_uuid)
        return application

    def list_confd_applications(self):
        if self._apps_cache is None:
            apps = self._confd.applications.list(recurse=True)['items']
            self._apps_cache = {app['uuid']: app for app in apps}
        return self._apps_cache.values()

    def get_call_id(self, application, call_id):
        if call_id not in application['channel_ids']:
            raise NoSuchCall(call_id)
        return call_id

    def delete_call(self, application_uuid, call_id):
        try:
            self._ari.channels.hangup(channelId=call_id)
        except ARINotFound:
            raise NoSuchCall(call_id)

    def delete_node(self, application_uuid, node):
        if str(node.uuid) == str(application_uuid):
            raise DeleteDestinationNode(application_uuid, node.uuid)

        for call in node.calls:
            try:
                self.delete_call(application_uuid, call.id_)
            except NoSuchCall:
                continue

        try:
            self._ari.bridges.destroy(bridgeId=node.uuid)
        except ARINotFound:
            pass  # The bridge has already disappeared

    def get_channel_variables(self, channel):
        command = 'core show channel {}'.format(channel.json['name'])
        result = self._amid.command(command)
        return {var: val for var, val in self._extract_variables(result['response'])}

    def get_node(self, application, node_uuid, verify_application=True):
        if verify_application:
            self.get_node_uuid(application, node_uuid)

        try:
            bridge = self._ari.bridges.get(bridgeId=node_uuid)
        except ARINotFound:
            raise NoSuchNode(node_uuid)

        return make_node_from_bridge(bridge)

    def get_node_uuid(self, application, node_uuid):
        # TODO: remove when asterisk will be able to create bridge associated to an application
        #       Otherwise, if the bridge doesn't received call, no bridge will appear in the
        #       application
        if application['uuid'] == node_uuid:
            return node_uuid

        if str(node_uuid) not in application['bridge_ids']:
            raise NoSuchNode(node_uuid)
        return node_uuid

    def join_destination_node(self, channel_id, application):
        self.join_node(application['uuid'], application['uuid'], [channel_id])
        moh = application['destination_options'].get('music_on_hold')
        if moh:
            self._ari.bridges.startMoh(bridgeId=application['uuid'], mohClass=moh)

    def join_node(self, application_uuid, node_uuid, call_ids, no_call_status_code=400):
        bridges = self._ari.bridges.list()
        self.validate_call_not_in_node(application_uuid, bridges, call_ids)

        for call_id in call_ids:
            try:
                self._ari.bridges.addChannel(bridgeId=node_uuid, channel=call_id)
            except ARINotFound:
                raise NoSuchNode(node_uuid)
            except HTTPError as e:
                response = getattr(e, 'response', None)
                status_code = getattr(response, 'status_code', None)
                if status_code == 400:
                    raise NoSuchCall(call_id, no_call_status_code)
                raise

    def validate_call_not_in_node(self, application_uuid, bridges, call_ids):
        for bridge in bridges:
            if str(bridge.id) == str(application_uuid):
                # Allow to switch channel from default bridge
                continue
            for call_id in call_ids:
                if call_id in bridge.json['channels']:
                    raise CallAlreadyInNode(application_uuid, bridge.id, call_id)

    def leave_node(self, application_uuid, node_uuid, call_id):
        try:
            self._ari.bridges.removeChannel(bridgeId=node_uuid, channel=call_id)
        except ARINotFound:
            raise NoSuchNode(node_uuid)
        except HTTPError as e:
            response = getattr(e, 'response', None)
            status_code = getattr(response, 'status_code', None)
            if status_code in (400, 422):
                raise NoSuchCall(call_id)
            raise

    def list_calls(self, application_uuid):
        try:
            channel_ids = self._ari.applications.get(
                applicationName=AppNameHelper.to_name(application_uuid)
            )['channel_ids']
        except ARINotFound:
            raise NoSuchApplication(application_uuid)

        for channel_id in channel_ids:
            try:
                channel = self._ari.channels.get(channelId=channel_id)
                variables = self.get_channel_variables(channel)
                yield make_call_from_channel(channel, ari=self._ari, variables=variables)
            except ARINotFound:
                continue

    def list_nodes(self, application_uuid):
        try:
            bridges = self._ari.bridges.list()
        except ARINotFound:
            return

        for bridge in bridges:
            if str(bridge.json['name']) != str(application_uuid):
                continue
            yield make_node_from_bridge(bridge)

    def originate(self, application_uuid, node_uuid, exten, context, autoanswer):
        if not ami.extension_exists(self._amid, context, exten, 1):
            raise InvalidExtension(context, exten)

        endpoint = 'Local/{}@{}/n'.format(exten, context)

        app_args = ['originate']
        if node_uuid:
            app_args.append(str(node_uuid))

        originate_kwargs = {
            'endpoint': endpoint,
            'app': AppNameHelper.to_name(application_uuid),
            'appArgs': ','.join(app_args),
            'variables': {'variables': {}}
        }

        if autoanswer:
            originate_kwargs['variables']['variables']['WAZO_AUTO_ANSWER'] = '1'

        channel = self._ari.channels.originate(**originate_kwargs)
        variables = self.get_channel_variables(channel)
        return make_call_from_channel(
            channel,
            ari=self._ari,
            variables=variables,
            node_uuid=node_uuid,
        )

    def originate_answered(self, application_uuid, channel):
        channel.answer()
        variables = self.get_channel_variables(channel)
        call = make_call_from_channel(channel, ari=self._ari, variables=variables)
        self._notifier.call_initiated(application_uuid, call)

    def start_call_moh(self, call_id, moh_uuid):
        moh = self._get_moh(moh_uuid)
        try:
            self._ari.channels.startMoh(channelId=call_id, mohClass=moh['name'])
        except ARINotFound:
            raise NoSuchCall(call_id)

    def stop_call_moh(self, call_id):
        try:
            self._ari.channels.stopMoh(channelId=call_id)
        except ARINotFound:
            raise NoSuchCall(call_id)

    def create_playback(self, application_uuid, call_id, media_uri, language=None):
        kwargs = {
            'channelId': call_id,
            'media': media_uri,
        }
        if language:
            kwargs['lang'] = language

        try:
            playback = self._ari.channels.play(**kwargs)
        except ARINotFound:
            raise NoSuchCall(call_id)

        try:
            playback.get()
        except ARINotFound:
            raise NoSuchMedia(media_uri)

        return playback.json

    def delete_playback(self, application_uuid, playback_id):
        try:
            self._ari.playbacks.stop(playbackId=playback_id)
        except ARINotFound:
            raise NoSuchPlayback(playback_id)

    def find_moh(self, moh_class):
        if self._moh_cache is None:
            self._fetch_moh()

        for moh in self._moh_cache:
            if moh['name'] == moh_class:
                return moh

    def _get_moh(self, moh_uuid):
        if self._moh_cache is None:
            self._fetch_moh()

        moh_uuid = str(moh_uuid)
        for moh in self._moh_cache:
            if moh['uuid'] == moh_uuid:
                return moh

        raise NoSuchMoh(moh_uuid)

    def _fetch_moh(self):
        self._moh_cache = self._confd.moh.list(recurse=True)['items']
        logger.info('MOH cache initialized: %s', self._moh_cache)

    @staticmethod
    def _extract_variables(lines):
        prefix = 'X_WAZO_'
        for line in lines:
            if not line.startswith(prefix):
                continue
            yield line.replace(prefix, '').split('=', 1)
