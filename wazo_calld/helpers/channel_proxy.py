# Copyright 2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from time import time

logger = logging.getLogger(__name__)

CHANNEL_CACHE_EXPIRATION = 60 * 60


class ChannelProxy:
    def __init__(self, ari):
        self._ari = ari
        self._channel_variable_cache = {}
        self._channel_json_cache = {}
        self._last_cache_cleanup = time()

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

    def on_hang_up(self, channel, event):
        self._remove_cached_channel(channel.id)
        self._remove_old_calls_from_cache()

    def _remove_old_calls_from_cache(self):
        # To avoid leaking channel variables if an event ever gets missed
        # we are going to clean the cache every once in a while
        now = time()
        threshold = now - CHANNEL_CACHE_EXPIRATION
        if self._last_cache_cleanup > threshold:
            return

        to_remove = set()
        for call_id in self._channel_variable_cache.keys():
            if float(call_id) < threshold:
                to_remove.add(call_id)

        for call_id in self._channel_json_cache.keys():
            if float(call_id) < threshold:
                to_remove.add(call_id)

        logger.debug('Removing %s calls from the cache', len(to_remove))
        for call_id in to_remove:
            self._remove_cached_channel(call_id)

        self._last_cache_cleanup = now

    def _remove_cached_channel(self, channel_id):
        logger.debug('removing %s from channel proxy', channel_id)
        self._channel_variable_cache.pop(channel_id, None)
        self._channel_json_cache.pop(channel_id, None)

    def _insert_value(self, channel_id, name, value):
        if channel_id not in self._channel_variable_cache:
            self._channel_variable_cache[channel_id] = {name: value}
        else:
            self._channel_variable_cache[channel_id][name] = value

    def _get_cached_value(self, channel_id, name):
        return self._channel_variable_cache[channel_id][name]
