# -*- coding: utf-8 -*-
# Copyright 2015-2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import json

from ari.exceptions import ARINotFound

from .exceptions import NotEnoughChannels
from .exceptions import TooManyChannels


class GlobalVariableAdapter(object):

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


class GlobalVariableJsonAdapter(object):

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


class GlobalVariableNameDecorator(object):

    def __init__(self, global_variables, variable_name_format):
        self._global_variables = global_variables
        self._format = variable_name_format

    def get(self, variable, default=None):
        return self._global_variables.get(self._format.format(variable), default)

    def set(self, variable, value):
        return self._global_variables.set(self._format.format(variable), value)

    def unset(self, variable):
        return self._global_variables.unset(self._format.format(variable))


class GlobalVariableConstantNameAdapter(object):

    def __init__(self, global_variables, variable_name):
        self._global_variables = global_variables
        self._variable = variable_name

    def get(self, default=None):
        return self._global_variables.get(self._variable, default)

    def set(self, value):
        return self._global_variables.set(self._variable, value)

    def unset(self):
        return self._global_variables.unset(self._variable)


class Channel(object):

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
            return connected_channels.pop().id
        except KeyError:
            raise NotEnoughChannels()

    def user(self, default=None):
        try:
            uuid = self._ari.channels.getChannelVar(channelId=self.id, variable='XIVO_USERUUID')['value']
            return uuid
        except ARINotFound:
            return default
