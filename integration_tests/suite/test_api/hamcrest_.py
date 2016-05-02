# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import is_in
from hamcrest import not_

from ari.exceptions import ARINotFound


class HamcrestARIChannel(object):
    def __init__(self, ari):
        self._ari = ari

    def is_in_bridge(self, type_=None):
        bridges = self._ari.bridges.list()
        if type_:
            bridges = (bridge for bridge in bridges if bridge.json['bridge_type'] == type_)
        channel_ids = (channel_id for bridge in bridges for channel_id in bridge.json['channels'])
        return is_in(list(channel_ids))

    def is_talking(self):
        channels = self._ari.channels.list()
        channel_ids = (channel.id for channel in channels if channel.json['state'] == 'Up')
        return is_in(list(channel_ids))

    def is_hungup(self):
        return not_(is_in(channel.id for channel in self._ari.channels.list()))

    def has_variable(self, variable, expected_value):
        channels = self._ari.channels.list()
        candidates = []
        for channel in channels:
            try:
                value = channel.getChannelVar(variable=variable)['value']
            except ARINotFound:
                continue
            if value == expected_value:
                candidates.append(channel.id)
        return is_in(candidates)


class HamcrestARIBridge(object):
    def __init__(self, ari):
        self._ari = ari

    def is_found(self):
        return is_in(bridge.id for bridge in self._ari.bridges.list())
