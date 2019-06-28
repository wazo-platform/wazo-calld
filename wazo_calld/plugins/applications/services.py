# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import time

from requests import HTTPError
from ari.exceptions import ARINotFound
from wazo_calld.helpers import ami
from wazo_calld.helpers import confd
from wazo_calld.helpers.exceptions import InvalidUserUUID
from wazo_calld.exceptions import InvalidExtension
from .models import (
    CallFormatter,
    make_node_from_bridge,
    SnoopHelper,
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


class ApplicationService:

    def __init__(self, ari, confd, amid, notifier, confd_apps):
        self._ari = ari
        self._confd = confd
        self._amid = amid
        self._notifier = notifier
        self._confd_apps = confd_apps
        self._moh_cache = None
        self._snoop_helper = SnoopHelper(self._ari)

    def call_mute(self, application, call_id):
        try:
            channel = self._ari.channels.get(channelId=call_id)
            self.set_channel_var_sync(channel, 'WAZO_CALL_MUTED', '1')
            channel.mute(direction='in')
        except ARINotFound:
            raise NoSuchCall(call_id)

        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel)
        self._notifier.call_updated(application['uuid'], call)

    def call_unmute(self, application, call_id):
        try:
            channel = self._ari.channels.get(channelId=call_id)
            self.set_channel_var_sync(channel, 'WAZO_CALL_MUTED', '')
            channel.unmute(direction='in')
        except ARINotFound:
            raise NoSuchCall(call_id)

        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel)
        self._notifier.call_updated(application['uuid'], call)

    def call_answer(self, application, call_id):
        try:
            channel = self._ari.channels.get(channelId=call_id)
        except ARINotFound:
            raise NoSuchCall(call_id)

        channel.answer()

    def start_user_outgoing_call(self, application, channel):
        self.set_channel_var_sync(channel, 'WAZO_USER_OUTGOING_CALL', 'true')
        variables = self.get_channel_variables(channel)
        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel, variables=variables)
        self._notifier.user_outgoing_call_created(application['uuid'], call)

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
            app_name = AppNameHelper.to_name(application['uuid'])
            self._ari.applications.subscribe(
                applicationName=app_name,
                eventSource='bridge:{}'.format(bridge.id),
            )
            node = make_node_from_bridge(bridge)
            self._notifier.destination_node_created(application['uuid'], node)

    def create_node_with_calls(self, application_uuid, call_ids):
        bridges = self._ari.bridges.list()
        self.validate_call_not_in_node(application_uuid, bridges, call_ids)

        stasis_app = AppNameHelper.to_name(application_uuid)
        bridge = self._ari.bridges.create(name=application_uuid, type='mixing')
        self._ari.applications.subscribe(
            applicationName=stasis_app,
            eventSource='bridge:{}'.format(bridge.id),
        )
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

        confd_app = self._confd_apps.get(application_uuid)
        node_uuid = application_uuid if confd_app['destination'] == 'node' else None

        application['destination_node_uuid'] = node_uuid
        application['uuid'] = application_uuid
        return application

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

    def join_destination_node(self, channel, application):
        answer = application['destination_options'].get('answer')
        if answer:
            channel.answer()

        self.join_node(application['uuid'], application['uuid'], [channel.id])
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

        formatter = CallFormatter(application, self._ari)
        for channel_id in application['channel_ids']:
            try:
                channel = self._ari.channels.get(channelId=channel_id)
            except ARINotFound:
                continue

            if is_wrong_side_of_local_channel(channel):
                continue

            variables = self.get_channel_variables(channel)
            yield formatter.from_channel(channel, variables=variables)

    def list_nodes(self, application_uuid):
        try:
            bridges = self._ari.bridges.list()
        except ARINotFound:
            return

        for bridge in bridges:
            if str(bridge.json['name']) != str(application_uuid):
                continue
            yield make_node_from_bridge(bridge)

    def originate(
            self,
            application,
            node_uuid,
            exten,
            context,
            autoanswer,
            displayed_caller_id_name,
            displayed_caller_id_number,
            variables=None,
    ):
        application_uuid = application['uuid']
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

        if displayed_caller_id_name or displayed_caller_id_number:
            # an empty cid number will result in "asterisk" being displayed
            number = displayed_caller_id_number or ' '
            callerid = '"{}" <{}>'.format(displayed_caller_id_name, number)
            originate_kwargs['callerId'] = callerid

        variables = variables or {}
        if autoanswer:
            variables['WAZO_AUTO_ANSWER'] = '1'

        for name, value in variables.items():
            originate_kwargs['variables']['variables'][name] = value

        channel = self._ari.channels.originate(**originate_kwargs)
        variables = self.get_channel_variables(channel)
        formatter = CallFormatter(application, self._ari)
        return formatter.from_channel(channel, variables=variables, node_uuid=node_uuid)

    def originate_user(
            self,
            application,
            node_uuid,
            user_uuid,
            autoanswer,
            displayed_caller_id_name,
            displayed_caller_id_number,
            variables=None,
    ):
        # check if user exists and has a line
        confd.User(user_uuid, self._confd).main_line()

        context = 'usersharedlines'
        exten = user_uuid

        return self.originate(
            application,
            node_uuid,
            exten,
            context,
            autoanswer,
            displayed_caller_id_name,
            displayed_caller_id_number,
            variables,
        )

    def originate_answered(self, application, channel):
        channel.answer()
        variables = self.get_channel_variables(channel)
        formatter = CallFormatter(application, self._ari)
        call = formatter.from_channel(channel, variables=variables)
        self._notifier.call_initiated(application['uuid'], call)

    def snoop_create(self, application, snooped_call_id, snooping_call_id, whisper_mode):
        snoop = self._snoop_helper.create(
            application,
            snooped_call_id,
            snooping_call_id,
            whisper_mode,
        )
        self._notifier.snoop_created(application['uuid'], snoop)
        return snoop

    def snoop_delete(self, application, snoop_uuid):
        return self._snoop_helper.delete(application, snoop_uuid)

    def snoop_edit(self, application, snoop_uuid, whisper_mode):
        snoop = self._snoop_helper.edit(application, snoop_uuid, whisper_mode)
        return snoop

    def snoop_get(self, application, snoop_uuid):
        snoop = self._snoop_helper.get(application, snoop_uuid)
        return snoop

    def snoop_list(self, application):
        snoops = self._snoop_helper.list_(application)
        return snoops

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

    def set_channel_var_sync(self, channel, var, value):
        # TODO remove this when Asterisk gets fixed to set var synchronously
        def get_value():
            try:
                return channel.getChannelVar(variable=var)['value']
            except ARINotFound as e:
                if e.original_error.response.reason == 'Variable Not Found':
                    return None
                raise

        channel.setChannelVar(variable=var, value=value)
        for _ in range(20):
            if get_value() == value:
                return

            logger.debug('waiting for a setvar to complete')
            time.sleep(0.01)

        raise Exception('failed to set channel variable {}={}'.format(var, value))

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
