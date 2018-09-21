# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from ari.exceptions import ARINotFound
from xivo_ctid_ng.helpers.ari_ import Channel as _ChannelHelper


class ApplicationCall(object):

    def __init__(self, id_):
        self.id_ = id_
        self.moh_uuid = None


class ApplicationNode(object):

    def __init__(self, uuid):
        self.uuid = uuid
        self.calls = []


def make_call_from_channel(channel, ari=None, variables=None, node_uuid=None):
    # TODO Merge channel_helper and channel object to avoid create another object
    # (ApplicationCall). Also set a cache system in that new object
    call = ApplicationCall(channel.id)
    call.creation_time = channel.json['creationtime']
    call.status = channel.json['state']
    call.caller_id_name = channel.json['caller']['name']
    call.caller_id_number = channel.json['caller']['number']

    if node_uuid:
        call.node_uuid = node_uuid

    if ari is not None:
        channel_helper = _ChannelHelper(channel.id, ari)
        call.on_hold = channel_helper.on_hold()
        call.is_caller = channel_helper.is_caller()
        call.dialed_extension = channel_helper.dialed_extension()
        try:
            call.moh_uuid = channel.getChannelVar(variable='WAZO_MOH_UUID').get('value') or None
        except ARINotFound:
            call.moh_uuid = None

        call.node_uuid = getattr(call, 'node_uuid', None)
        for bridge in ari.bridges.list():
            if channel.id in bridge.json['channels']:
                call.node_uuid = bridge.id
                break

    if variables is not None:
        call.variables = variables

    return call


def make_node_from_bridge(bridge):
    node = ApplicationNode(bridge.id)
    for channel_id in bridge.json['channels']:
        node.calls.append(ApplicationCall(channel_id))
    return node


def make_node_from_bridge_event(bridge):
    node = ApplicationNode(bridge['id'])
    for channel_id in bridge['channels']:
        node.calls.append(ApplicationCall(channel_id))
    return node
