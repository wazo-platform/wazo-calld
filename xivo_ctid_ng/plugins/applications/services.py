# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging
from uuid import uuid4

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
    NoSuchSnoop,
)
from .stasis import AppNameHelper

logger = logging.getLogger(__name__)


class _Snoop(object):

    _bridge_name_tpl = 'wazo-app-snoop-{}'
    _snooped_call_id_chan_var = 'WAZO_SNOOPED_CALL_ID'
    _whisper_mode_chan_var = 'WAZO_SNOOP_WHISPER_MODE'

    def __init__(self, application, snooped_call_id, snooping_call_id, whisper_mode, **kwargs):
        self.uuid = kwargs.get('uuid') or str(uuid4())
        self.application = application
        self.snooped_call_id = snooped_call_id
        self.snooping_call_id = snooping_call_id
        self.whisper_mode = whisper_mode
        self.bridge_name = self._bridge_name_tpl.format(application['uuid'])
        self._bridge = None
        self._snoop_channel = None

    def create_bridge(self, ari):
        self._bridge = ari.bridges.createWithId(
            bridgeId=self.uuid,
            name=self.bridge_name,
            type='mixing',
        )

        self._bridge.addChannel(channel=self._snoop_channel.id)
        try:
            self._bridge.addChannel(channel=self.snooping_call_id)
        except HTTPError as e:
            response = getattr(e, 'response', None)
            status_code = getattr(response, 'status_code', None)
            if status_code == 400:
                raise NoSuchCall(self.snooping_call_id, status_code=400)
            raise

    def create_snoop_channel(self, ari):
        try:
            self._snoop_channel = ari.channels.snoopChannelWithId(
                channelId=self.snooped_call_id,
                snoopId=self.uuid,
                spy='both',
                whisper=self.whisper_mode,
                app=self.application['name'],
            )
        except ARINotFound:
            raise NoSuchCall(self.snooped_call_id)

    def destroy(self):
        if self._bridge:
            try:
                self._bridge.destroy()
            except ARINotFound:
                pass

        if self._snoop_channel:
            try:
                self._snoop_channel.hangup()
            except ARINotFound:
                pass

    def validate_ownership(self, application, snooped_call_id, snooping_call_id):
        if snooped_call_id not in application['channel_ids']:
            raise NoSuchCall(snooped_call_id, status_code=404)
        if snooping_call_id not in application['channel_ids']:
            raise NoSuchCall(snooping_call_id, status_code=400)

    def save_properties(self):
        self._snoop_channel.setChannelVar(
            variable=self._snooped_call_id_chan_var,
            value=self.snooped_call_id
        )
        self._snoop_channel.setChannelVar(
            variable=self._whisper_mode_chan_var,
            value=self.whisper_mode,
        )

    @classmethod
    def from_bridge(cls, ari, application, bridge):
        for channel_id in bridge.json['channels']:
            if channel_id == bridge.id:
                snoop_channel = ari.channels.get(channelId=channel_id)
            else:
                snooping_call_id = channel_id

        snooped_call_id = cls.get_snooped_call_id(snoop_channel)
        whisper_mode = cls.get_whisper_mode(snoop_channel)
        snoop = cls(application, snooped_call_id, snooping_call_id, whisper_mode, uuid=bridge.id)
        return snoop

    @classmethod
    def get_snooped_call_id(cls, snoop_channel):
        return snoop_channel.getChannelVar(variable=cls._snooped_call_id_chan_var)['value']

    @classmethod
    def get_whisper_mode(cls, snoop_channel):
        return snoop_channel.getChannelVar(variable=cls._whisper_mode_chan_var)['value']


class _SnoopHelper(object):

    def __init__(self, ari):
        self._ari = ari

    def create(self, application, snooped_call_id, snooping_call_id, whisper_mode):
        snoop = _Snoop(application, snooped_call_id, snooping_call_id, whisper_mode)
        snoop.validate_ownership(application, snooped_call_id, snooping_call_id)
        try:
            snoop.create_snoop_channel(self._ari)
            snoop.create_bridge(self._ari)
            snoop.save_properties()
        except Exception:
            snoop.destroy()
            raise
        return snoop

    def get(self, application, snoop_uuid):
        uuid = str(snoop_uuid)
        for snoop_bridge in self._find_snoop_channels(application):
            if snoop_bridge.id != uuid:
                continue

            return _Snoop.from_bridge(self._ari, application, snoop_bridge)

        raise NoSuchSnoop(snoop_uuid)

    def _find_snoop_channels(self, application):
        bridge_name = 'wazo-app-snoop-{}'.format(str(application['uuid']))
        for bridge in self._ari.bridges.list():
            if bridge.json['name'] == bridge_name:
                yield bridge


class ApplicationService(object):

    def __init__(self, ari, confd, amid, notifier):
        self._ari = ari
        self._confd = confd
        self._amid = amid
        self._notifier = notifier
        self._apps_cache = None
        self._moh_cache = None
        self._snoop_helper = _SnoopHelper(self._ari)

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
                app=AppNameHelper.to_name(application['uuid']),
                bridgeId=application['uuid'],
                name=application['uuid'],
                type=bridge_type,
            )
            node = make_node_from_bridge(bridge)
            self._notifier.destination_node_created(application['uuid'], node)

    def create_node_with_calls(self, application_uuid, call_ids):
        bridges = self._ari.bridges.list()
        self.validate_call_not_in_node(application_uuid, bridges, call_ids)

        stasis_app = AppNameHelper.to_name(application_uuid)
        bridge = self._ari.bridges.create(app=stasis_app, name=application_uuid, type='mixing')
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

        confd_app = self.get_confd_application(application_uuid)
        node_uuid = application_uuid if confd_app['destination'] == 'node' else None

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

    def get_call_id(self, application, call_id, status_code=404):
        if call_id not in application['channel_ids']:
            raise NoSuchCall(call_id, status_code)
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

    def list_calls(self, application):
        def is_wrong_side_of_local_channel(channel):
            name = channel.json['name']
            return name.startswith('Local/') and name.endswith(';2')

        for channel_id in application['channel_ids']:
            try:
                channel = self._ari.channels.get(channelId=channel_id)
            except ARINotFound:
                continue

            if is_wrong_side_of_local_channel(channel):
                continue

            variables = self.get_channel_variables(channel)
            yield make_call_from_channel(channel, ari=self._ari, variables=variables)

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

    def snoop_create(self, application, snooped_call_id, snooping_call_id, whisper_mode):
        snoop = self._snoop_helper.create(
            application,
            snooped_call_id,
            snooping_call_id,
            whisper_mode,
        )
        return snoop

    def snoop_get(self, application, snoop_uuid):
        snoop = self._snoop_helper.get(application, snoop_uuid)
        return snoop

    def start_call_hold(self, call_id):
        try:
            self._ari.channels.setChannelVar(channelId=call_id, variable='XIVO_ON_HOLD', value='1')
            self._ari.channels.mute(channelId=call_id, direction='in')
            self._ari.channels.hold(channelId=call_id)
        except ARINotFound:
            raise NoSuchCall(call_id)

    def stop_call_hold(self, call_id):
        try:
            self._ari.channels.setChannelVar(channelId=call_id, variable='XIVO_ON_HOLD', value='')
            self._ari.channels.unmute(channelId=call_id, direction='in')
            self._ari.channels.unhold(channelId=call_id)
        except ARINotFound:
            raise NoSuchCall(call_id)

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
