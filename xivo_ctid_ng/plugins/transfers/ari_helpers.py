# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import json

from ari.exceptions import ARINotFound, ARINotInStasis

from . import ami_helpers


def is_in_stasis(ari, call_id):
    try:
        ari.channels.setChannelVar(channelId=call_id, variable='XIVO_TEST_STASIS')
        return True
    except ARINotInStasis:
        return False


def hold_transferred_call(ari, transferred_call):
    ari.channels.mute(channelId=transferred_call, direction='in')
    ari.channels.hold(channelId=transferred_call)
    ari.channels.startMoh(channelId=transferred_call)


def unhold_transferred_call(ari, transferred_call):
    ari.channels.unmute(channelId=transferred_call, direction='in')
    ari.channels.unhold(channelId=transferred_call)
    ari.channels.stopMoh(channelId=transferred_call)


def unring_initiator_call(ari, initiator_call):
    ari.channels.stopMoh(channelId=initiator_call)  # workaround for SCCP bug on ringStop
    ari.channels.ringStop(channelId=initiator_call)


def unset_variable(ari, amid, channel_id, variable):
    try:
        ari.channels.setChannelVar(channelId=channel_id, variable=variable, value='')
    except ARINotFound:
        pass
    except ARINotInStasis:
        ami_helpers.unset_variable_ami(amid, channel_id, variable)


def update_connectedline(ari, amid, channel_id, from_channel_id):
    from_channel = ari.channels.get(channelId=from_channel_id)
    name = from_channel.json['caller']['name']
    number = from_channel.json['caller']['number']
    ari.channels.setChannelVar(channelId=channel_id, variable='CONNECTEDLINE(name)', value=name.encode('utf-8'))
    ari.channels.setChannelVar(channelId=channel_id, variable='CONNECTEDLINE(num)', value=number.encode('utf-8'))


def set_bridge_variable(ari, bridge_id, variable, value):
    global_variable = 'XIVO_BRIDGE_VARIABLES_{}'.format(bridge_id)
    try:
        cache_str = ari.asterisk.getGlobalVar(variable=global_variable)['value']
    except ARINotFound:
        cache_str = '{}'
    if not cache_str:
        cache_str = '{}'
    cache = json.loads(cache_str)

    cache[variable] = value

    ari.asterisk.setGlobalVar(variable=global_variable, value=json.dumps(cache))


def get_bridge_variable(ari, bridge_id, variable):
    global_variable = 'XIVO_BRIDGE_VARIABLES_{}'.format(bridge_id)
    try:
        cache_str = ari.asterisk.getGlobalVar(variable=global_variable)['value']
    except ARINotFound:
        cache_str = '{}'
    if not cache_str:
        cache_str = '{}'
    cache = json.loads(cache_str)

    try:
        return cache[variable]
    except KeyError as e:
        raise ARINotFound(ari, e)


def channel_exists(ari, channel_id):
    try:
        ari.channels.get(channelId=channel_id)
        return True
    except ARINotFound:
        return False
