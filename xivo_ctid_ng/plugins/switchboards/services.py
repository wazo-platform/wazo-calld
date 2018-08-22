# -*- coding: utf-8 -*-
# Copyright 2017-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from ari.exceptions import ARINotFound

from xivo.caller_id import assemble_caller_id
from xivo_ctid_ng.ari_ import DEFAULT_APPLICATION_NAME
from xivo_ctid_ng.helpers.confd import User

from .call import (
    HeldCall,
    QueuedCall,
)
from .confd import Switchboard
from .exceptions import (
    NoSuchCall,
    NoSuchSwitchboard,
)

BRIDGE_QUEUE_ID = 'switchboard-{uuid}-queue'
BRIDGE_HOLD_ID = 'switchboard-{uuid}-hold'

logger = logging.getLogger(__name__)


class SwitchboardsService(object):

    def __init__(self, ari, confd, notifier):
        self._ari = ari
        self._confd = confd
        self._notifier = notifier

    def queued_calls(self, switchboard_uuid):
        if not Switchboard(switchboard_uuid, self._confd).exists():
            raise NoSuchSwitchboard(switchboard_uuid)

        bridge_id = BRIDGE_QUEUE_ID.format(uuid=switchboard_uuid)
        try:
            bridge = self._ari.bridges.get(bridgeId=bridge_id)
        except ARINotFound:
            return []

        channel_ids = bridge.json.get('channels', None)

        result = []
        for channel_id in channel_ids:
            channel = self._ari.channels.get(channelId=channel_id)

            call = QueuedCall(channel.id)
            call.caller_id_name = channel.json['caller']['name']
            call.caller_id_number = channel.json['caller']['number']

            result.append(call)
        return result

    def new_queued_call(self, switchboard_uuid, channel_id):
        bridge_id = BRIDGE_QUEUE_ID.format(uuid=switchboard_uuid)
        try:
            bridge = self._ari.bridges.get(bridgeId=bridge_id)
        except ARINotFound:
            bridge = self._ari.bridges.createWithId(type='holding', bridgeId=bridge_id)

        if len(bridge.json['channels']) == 0:
            bridge.startMoh()

        channel = self._ari.channels.get(channelId=channel_id)
        channel.setChannelVar(variable='WAZO_SWITCHBOARD_QUEUE', value=switchboard_uuid)
        channel.answer()
        bridge.addChannel(channel=channel_id)

        self._notifier.queued_calls(switchboard_uuid, self.queued_calls(switchboard_uuid))

    def answer_queued_call(self, switchboard_uuid, queued_call_id, user_uuid):
        if not Switchboard(switchboard_uuid, self._confd).exists():
            raise NoSuchSwitchboard(switchboard_uuid)

        try:
            queued_channel = self._ari.channels.get(channelId=queued_call_id)
        except ARINotFound:
            raise NoSuchCall(queued_call_id)

        endpoint = User(user_uuid, self._confd).main_line().interface()
        caller_id = assemble_caller_id(
            queued_channel.json['caller']['name'],
            queued_channel.json['caller']['number']
        ).encode('utf-8')

        channel = self._ari.channels.originate(
            endpoint=endpoint,
            app=DEFAULT_APPLICATION_NAME,
            appArgs=['switchboard', 'switchboard_answer', switchboard_uuid, queued_call_id],
            callerId=caller_id,
            originator=queued_call_id,
        )

        return channel.id

    def hold_call(self, switchboard_uuid, call_id):
        if not Switchboard(switchboard_uuid, self._confd).exists():
            raise NoSuchSwitchboard(switchboard_uuid)

        try:
            channel_to_hold = self._ari.channels.get(channelId=call_id)
        except ARINotFound:
            raise NoSuchCall(call_id)

        previous_bridges = [bridge for bridge in self._ari.bridges.list()
                            if channel_to_hold.id in bridge.json['channels']]

        hold_bridge_id = BRIDGE_HOLD_ID.format(uuid=switchboard_uuid)
        try:
            hold_bridge = self._ari.bridges.get(bridgeId=hold_bridge_id)
        except ARINotFound:
            hold_bridge = self._ari.bridges.createWithId(type='holding', bridgeId=hold_bridge_id)

        if len(hold_bridge.json['channels']) == 0:
            hold_bridge.startMoh()

        hold_bridge.addChannel(channel=channel_to_hold.id)
        channel_to_hold.setChannelVar(variable='WAZO_SWITCHBOARD_HOLD', value=switchboard_uuid)

        held_calls = self.held_calls(switchboard_uuid)
        self._notifier.held_calls(switchboard_uuid, held_calls)

        for previous_bridge in previous_bridges:
            try:
                previous_bridge = self._ari.bridges.get(bridgeId=previous_bridge.id)
            except ARINotFound:
                continue
            if previous_bridge.json['bridge_type'] == 'mixing' and len(previous_bridge.json['channels']) <= 1:
                logger.debug('emptying bridge %s after switchboard hold', previous_bridge.id)
                for lone_channel_id in previous_bridge.json['channels']:
                    logger.debug('hanging up channel %s after switchboard hold', lone_channel_id)
                    try:
                        self._ari.channels.hangup(channelId=lone_channel_id)
                    except ARINotFound:
                        pass

    def held_calls(self, switchboard_uuid):
        if not Switchboard(switchboard_uuid, self._confd).exists():
            raise NoSuchSwitchboard(switchboard_uuid)

        bridge_id = BRIDGE_HOLD_ID.format(uuid=switchboard_uuid)
        try:
            bridge = self._ari.bridges.get(bridgeId=bridge_id)
        except ARINotFound:
            return []

        channel_ids = bridge.json.get('channels', None)

        result = []
        for channel_id in channel_ids:
            channel = self._ari.channels.get(channelId=channel_id)

            call = HeldCall(channel.id)
            call.caller_id_name = channel.json['caller']['name']
            call.caller_id_number = channel.json['caller']['number']

            result.append(call)
        return result

    def answer_held_call(self, switchboard_uuid, held_call_id, user_uuid):
        if not Switchboard(switchboard_uuid, self._confd).exists():
            raise NoSuchSwitchboard(switchboard_uuid)

        try:
            held_channel = self._ari.channels.get(channelId=held_call_id)
        except ARINotFound:
            raise NoSuchCall(held_call_id)

        endpoint = User(user_uuid, self._confd).main_line().interface()
        caller_id = assemble_caller_id(
            held_channel.json['caller']['name'],
            held_channel.json['caller']['number'],
        ).encode('utf-8')

        channel = self._ari.channels.originate(
            endpoint=endpoint,
            app=DEFAULT_APPLICATION_NAME,
            appArgs=['switchboard', 'switchboard_unhold', switchboard_uuid, held_call_id],
            callerId=caller_id,
        )

        return channel.id
