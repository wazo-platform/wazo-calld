# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import json

from ari.exceptions import ARINotFound, ARINotInStasis

from .exceptions import (
    NotEnoughChannels,
    TooManyChannels,
)


class GlobalVariableAdapter:

    def __init__(self, ari_client):
        self._ari = ari_client

    def get(self, variable, default=None):
        try:
            return self._ari.asterisk.getGlobalVar(variable=variable)['value']
        except ARINotFound:
            if default is None:
                raise KeyError(variable)
            return default

    def set(self, variable, value):
        self._ari.asterisk.setGlobalVar(variable=variable, value=value)

    def unset(self, variable):
        self._ari.asterisk.setGlobalVar(variable=variable, value='')


class GlobalVariableJsonAdapter:

    def __init__(self, global_variables):
        self._global_variables = global_variables

    def get(self, variable, default=None):
        value = self._global_variables.get(variable)
        if not value:
            if default is None:
                raise KeyError(variable)
            return default
        return json.loads(value)

    def set(self, variable, value):
        self._global_variables.set(variable, json.dumps(value))

    def unset(self, variable):
        self._global_variables.unset(variable)


class GlobalVariableNameDecorator:

    def __init__(self, global_variables, variable_name_format):
        self._global_variables = global_variables
        self._format = variable_name_format

    def get(self, variable, default=None):
        return self._global_variables.get(self._format.format(variable), default)

    def set(self, variable, value):
        return self._global_variables.set(self._format.format(variable), value)

    def unset(self, variable):
        return self._global_variables.unset(self._format.format(variable))


class GlobalVariableConstantNameAdapter:

    def __init__(self, global_variables, variable_name):
        self._global_variables = global_variables
        self._variable = variable_name

    def get(self, default=None):
        return self._global_variables.get(self._variable, default)

    def set(self, value):
        return self._global_variables.set(self._variable, value)

    def unset(self):
        return self._global_variables.unset(self._variable)


class Channel:

    def __init__(self, channel_id, ari):
        self.id = channel_id
        self._ari = ari

    def __str__(self):
        return self.id

    def connected_channels(self):
        channel_ids = set(sum((bridge.json['channels'] for bridge in self._ari.bridges.list()
                               if self.id in bridge.json['channels']), list()))
        try:
            channel_ids.remove(self.id)
        except KeyError:
            pass
        return {Channel(channel_id, self._ari) for channel_id in channel_ids}

    def only_connected_channel(self):
        connected_channels = self.connected_channels()
        if len(connected_channels) > 1:
            raise TooManyChannels(channel.id for channel in connected_channels)
        try:
            channel_id = connected_channels.pop().id
        except KeyError:
            raise NotEnoughChannels()
        return Channel(channel_id, self._ari)

    def user(self, default=None):
        if self.is_local():
            try:
                uuid = self._get_var('WAZO_DEREFERENCED_USERUUID')
            except ARINotFound:
                return default
            return uuid

        try:
            uuid = self._get_var('XIVO_USERUUID')
            return uuid
        except ARINotFound:
            return default

    def exists(self):
        try:
            self._ari.channels.get(channelId=self.id)
            return True
        except ARINotFound:
            return False

    def is_local(self):
        try:
            channel = self._ari.channels.get(channelId=self.id)
        except ARINotFound:
            return False

        return channel.json['name'].startswith('Local/')

    def is_caller(self):
        try:
            direction = self._get_var('WAZO_CHANNEL_DIRECTION')
            return direction == 'to-wazo'
        except ARINotFound:
            return False

    def is_in_stasis(self):
        try:
            self._ari.channels.setChannelVar(channelId=self.id, variable='WAZO_TEST_STASIS')
            return True
        except ARINotInStasis:
            return False

    def is_sip(self):
        try:
            return self._get_var('CHANNEL(channeltype)') == 'PJSIP'
        except ARINotFound:
            return False

    def dialed_extension(self):
        try:
            channel = self._ari.channels.get(channelId=self.id)
        except ARINotFound:
            return

        try:
            return channel.getChannelVar(variable='XIVO_BASE_EXTEN')['value']
        except ARINotFound:
            return channel.json['dialplan']['exten']

    def on_hold(self):
        try:
            on_hold = self._get_var('XIVO_ON_HOLD')
            return on_hold == '1'
        except ARINotFound:
            return False

    def sip_call_id(self):
        if not self.is_sip():
            return

        try:
            return self._get_var('CHANNEL(pjsip,call-id)')
        except ARINotFound:
            return

    def _get_var(self, var):
        return self._ari.channels.getChannelVar(channelId=self.id, variable=var)['value']
