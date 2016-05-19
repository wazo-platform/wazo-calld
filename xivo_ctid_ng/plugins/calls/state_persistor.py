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


class ReadOnlyStatePersistor(object):
    def __init__(self, ari):
        self._ari = ari

    def get(self, channel_id):
        try:
            entry_str = self._ari.asterisk.getGlobalVar(variable=self._var_name(channel_id))['value']
        except ARINotFound:
            raise KeyError(channel_id)
        if not entry_str:
            raise KeyError(channel_id)

        return ChannelCacheEntry.from_dict(json.loads(entry_str))

    def _var_name(self, channel_id):
        return 'XIVO_CHANNELS_{}'.format(channel_id)


class StatePersistor(ReadOnlyStatePersistor):

    def upsert(self, channel_id, entry):
        self._ari.asterisk.setGlobalVar(variable=self._var_name(channel_id), value=json.dumps(entry.to_dict()))

    def remove(self, channel_id):
        self._ari.asterisk.setGlobalVar(variable=self._var_name(channel_id), value='')
