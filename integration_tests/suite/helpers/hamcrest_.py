# Copyright 2016-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from datetime import datetime

from ari.exceptions import ARINotFound
from hamcrest import all_of, instance_of, is_in, not_
from hamcrest.core.base_matcher import BaseMatcher


class HamcrestARIChannel:
    def __init__(self, ari):
        self._ari = ari

    def is_in_bridge(self, type_=None):
        bridges = self._ari.bridges.list()
        if type_:
            bridges = (
                bridge for bridge in bridges if bridge.json['bridge_type'] == type_
            )
        channel_ids = (
            channel_id for bridge in bridges for channel_id in bridge.json['channels']
        )
        return is_in(list(channel_ids))

    def is_talking(self):
        channels = self._ari.channels.list()
        channel_ids = (
            channel.id for channel in channels if channel.json['state'] == 'Up'
        )
        return is_in(list(channel_ids))

    def is_ringback(self):
        # There is currently no way to tell if a channel is ringback or not. It is considered Up.
        channels = self._ari.channels.list()
        channel_ids = (
            channel.id for channel in channels if channel.json['state'] == 'Up'
        )
        return is_in(list(channel_ids))

    def is_ringing(self):
        channels = self._ari.channels.list()
        channel_ids = (
            channel.id for channel in channels if channel.json['state'] == 'Ringing'
        )
        return is_in(list(channel_ids))

    def is_hungup(self):
        channel_ids = (channel.id for channel in self._ari.channels.list())
        return all_of(instance_of(str), not_(is_in(list(channel_ids))))

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


class HamcrestARIBridge:
    def __init__(self, ari):
        self._ari = ari

    def is_found(self):
        bridge_ids = (bridge.id for bridge in self._ari.bridges.list())
        return is_in(list(bridge_ids))


class ATimeStamp(BaseMatcher):
    def _matches(self, item):
        try:
            datetime.fromisoformat(item)
            return True
        except (ValueError, TypeError):
            return False

    def describe_to(self, description):
        description.append_text('a valid date')


def a_timestamp():
    return ATimeStamp()
