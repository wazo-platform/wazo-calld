# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo_ctid_ng.core.ari_ import APPLICATION_NAME
from xivo_ctid_ng.core.ari_helpers import Channel
from xivo_ctid_ng.core.confd_helpers import User
from ari.exceptions import ARINotFound

from .call import Call
from .exceptions import CallConnectError
from .exceptions import NoSuchCall
from .state_persistor import ReadOnlyStatePersistor

logger = logging.getLogger(__name__)


class CallsService(object):

    def __init__(self, ari_config, ari, confd_client):
        self._ari_config = ari_config
        self._ari = ari
        self._confd = confd_client
        self._state_persistor = ReadOnlyStatePersistor(self._ari)

    def list_calls(self, application_filter=None, application_instance_filter=None):
        channels = self._ari.channels.list()

        if application_filter:
            try:
                channel_ids = self._ari.applications.get(applicationName=application_filter)['channel_ids']
            except ARINotFound:
                channel_ids = []

            channels = [channel for channel in channels if channel.id in channel_ids]

            if application_instance_filter:
                app_instance_channels = []
                for channel in channels:
                    try:
                        channel_app_instance = self._state_persistor.get(channel.id).app_instance
                    except KeyError:
                        continue
                    if channel_app_instance == application_instance_filter:
                        app_instance_channels.append(channel)
                channels = app_instance_channels

        return [self.make_call_from_channel(self._ari, channel) for channel in channels]

    def originate(self, request):
        source_user = request['source']['user']
        endpoint = User(source_user, self._confd).main_line().interface()
        variables = request.get('variables', {})
        variables.setdefault('CONNECTEDLINE(all)', request['destination']['extension'])

        channel = self._ari.channels.originate(endpoint=endpoint,
                                               extension=request['destination']['extension'],
                                               context=request['destination']['context'],
                                               priority=request['destination']['priority'],
                                               variables={'variables': variables})
        return channel.id

    def originate_user(self, request, user_uuid):
        context = User(user_uuid, self._confd).main_line().context()
        new_request = {
            'destination': {'context': context,
                            'extension': request['extension'],
                            'priority': 1},
            'source': {'user': user_uuid},
            'variables': request['variables']
        }
        return self.originate(new_request)

    def get(self, call_id):
        channel_id = call_id
        try:
            channel = self._ari.channels.get(channelId=channel_id)
        except ARINotFound:
            raise NoSuchCall(channel_id)

        return self.make_call_from_channel(self._ari, channel)

    def hangup(self, call_id):
        channel_id = call_id
        try:
            self._ari.channels.get(channelId=channel_id)
        except ARINotFound:
            raise NoSuchCall(channel_id)

        self._ari.channels.hangup(channelId=channel_id)

    def connect_user(self, call_id, user_uuid):
        channel_id = call_id
        endpoint = User(user_uuid, self._confd).main_line().interface()

        try:
            channel = self._ari.channels.get(channelId=channel_id)
        except ARINotFound:
            raise NoSuchCall(channel_id)

        try:
            app_instance = self._state_persistor.get(channel_id).app_instance
        except KeyError:
            raise CallConnectError(call_id)

        new_channel = self._ari.channels.originate(endpoint=endpoint,
                                                   app=APPLICATION_NAME,
                                                   appArgs=[app_instance, 'dialed_from', channel_id])

        # if the caller hangs up, we cancel our originate
        originate_canceller = channel.on_event('StasisEnd', lambda _, __: self.hangup(new_channel.id))
        # if the callee accepts, we don't have to cancel anything
        new_channel.on_event('StasisStart', lambda _, __: originate_canceller.close())
        # if the callee refuses, leave the caller as it is

        return new_channel.id

    def make_call_from_channel(self, ari, channel):
        call = Call(channel.id)
        call.creation_time = channel.json['creationtime']
        call.status = channel.json['state']
        call.caller_id_name = channel.json['caller']['name']
        call.caller_id_number = channel.json['caller']['number']
        call.user_uuid = Channel(channel.id, ari).user()
        call.on_hold = self._get_hold_from_channel_id(ari, channel.id) == '1'
        call.bridges = [bridge.id for bridge in ari.bridges.list() if channel.id in bridge.json['channels']]
        call.talking_to = {connected_channel.id: connected_channel.user()
                           for connected_channel in Channel(channel.id, ari).connected_channels()}

        return call

    def make_call_from_ami_event(self, event):
        call = Call(event['Uniqueid'])
        call.status = event['ChannelStateDesc']
        call.caller_id_name = event['CallerIDName']
        call.caller_id_number = event['CallerIDNum']
        call.user_uuid = event.get('XIVO_USERUUID') or None
        call.bridges = []
        call.talking_to = {}

        return call

    def _get_hold_from_channel_id(self, ari, channel_id):
        try:
            return ari.channels.getChannelVar(channelId=channel_id, variable='XIVO_ON_HOLD')['value']
        except ARINotFound:
            return None
