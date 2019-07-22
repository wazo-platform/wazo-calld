# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_calld.helpers.ari_ import (GlobalVariableAdapter,
                                     GlobalVariableJsonAdapter,
                                     GlobalVariableNameDecorator)


class ChannelCacheEntry:
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


class ReadOnlyStatePersistor:
    def __init__(self, ari):
        self._channels = GlobalVariableNameDecorator(GlobalVariableJsonAdapter(GlobalVariableAdapter(ari)),
                                                     'XIVO_CHANNELS_{}')

    def get(self, channel_id):
        return ChannelCacheEntry.from_dict(self._channels.get(channel_id))


class StatePersistor(ReadOnlyStatePersistor):

    def upsert(self, channel_id, entry):
        self._channels.set(channel_id, entry.to_dict())

    def remove(self, channel_id):
        self._channels.unset(channel_id)
