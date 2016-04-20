# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import json

from ari.exceptions import ARINotFound


class ChannelCacheEntry(object):
    def __init__(self, app, app_instance, state):
        self.app = app
        self.app_instance = app_instance
        self.state = state

    def to_dict(self):
        return {'app': self.app,
                'app_instance': self.app_instance,
                'state': self.state}

    @classmethod
    def from_dict(cls, dict_):
        return cls(app=dict_['app'],
                   app_instance=dict_['app_instance'],
                   state=dict_['state'])


class StatePersistor(object):
    global_var_name = 'XIVO_CALLCONTROL'

    def __init__(self, ari):
        self._ari = ari

    def get(self, channel_id):
        return ChannelCacheEntry.from_dict(self._cache()[channel_id])

    def upsert(self, channel_id, entry):
        cache = self._cache()
        cache[channel_id] = entry.to_dict()
        self._set_cache(cache)

    def remove(self, channel_id):
        cache = self._cache()
        cache.pop(channel_id, None)
        self._set_cache(cache)

    def _cache(self):
        try:
            cache_str = self._ari.asterisk.getGlobalVar(variable=self.global_var_name)['value']
        except ARINotFound:
            return {}
        if not cache_str:
            return {}
        return json.loads(cache_str)

    def _set_cache(self, cache):
        self._ari.asterisk.setGlobalVar(variable=self.global_var_name,
                                        value=json.dumps(cache))
