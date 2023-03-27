# Copyright 2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


class ChannelProxy:
    def __init__(self, ari):
        self._ari = ari
        self._channel_variable_cache = {}
        self._channel_json_cache = {}

    def get_variable(self, channel_id, name):
        response = self._ari.channels.getChannelVar(channelId=channel_id, variable=name)
        return response['value']

    def get_constant(self, channel_id, name):
        try:
            result = self._get_cached_value(channel_id, name)
        except KeyError:
            result = self.get_variable(channel_id, name)
            self._insert_value(channel_id, name, result)
        return result

    def get_constant_json(self, channel_id):
        try:
            result = self._channel_json_cache[channel_id]
        except KeyError:
            channel = self._ari.channels.get(channelId=channel_id)
            result = channel.json
            self._channel_json_cache[channel_id] = result
        return result

    def _insert_value(self, channel_id, name, value):
        if channel_id not in self._channel_variable_cache:
            self._channel_variable_cache[channel_id] = {name: value}
        else:
            self._channel_variable_cache[channel_id][name] = value

    def _get_cached_value(self, channel_id, name):
        return self._channel_variable_cache[channel_id][name]
