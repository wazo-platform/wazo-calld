# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from ari.exceptions import ARINotFound

from xivo.caller_id import assemble_caller_id
from wazo_calld.ari_ import DEFAULT_APPLICATION_NAME
from wazo_calld.plugin_helpers.confd import User
from wazo_calld.plugin_helpers.exceptions import InvalidUserUUID

from .call import (
    HeldCall,
    QueuedCall,
)
from .confd import Switchboard
from .exceptions import (
    NoSuchCall,
    NoSuchSwitchboard,
    NoSuchConfdUser,
)

BRIDGE_QUEUE_ID = 'switchboard-{uuid}-queue'
BRIDGE_HOLD_ID = 'switchboard-{uuid}-hold'
AUTO_ANSWER_VARIABLES = {
    # Aastra/Mitel need Alert-Info: info=alert-autoanswer
    # Polycom need Alert-Info: xivo-autoanswer
    # Snom need Alert-Info: <http://something>;info=alert-autoanswer;delay=0
    # Which models need the other headers is unknown
    'PJSIP_HEADER(add,Alert-Info)': '<http://wazo.community>;info=alert-autoanswer;delay=0;xivo-autoanswer',
    'PJSIP_HEADER(add,Answer-After)': '0',
    'PJSIP_HEADER(add,Answer-Mode)': 'Auto',
    'PJSIP_HEADER(add,Call-Info)': ';answer-after=0',
    'PJSIP_HEADER(add,P-Auto-answer)': 'normal',
}

logger = logging.getLogger(__name__)


class SwitchboardsService:

    def __init__(self, ari, confd, notifier):
        self._ari = ari
        self._confd = confd
        self._notifier = notifier

    def queued_calls(self, tenant_uuid, switchboard_uuid):
        if not Switchboard(tenant_uuid, switchboard_uuid, self._confd).exists():
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

    def new_queued_call(self, tenant_uuid, switchboard_uuid, channel_id):
        bridge_id = BRIDGE_QUEUE_ID.format(uuid=switchboard_uuid)
        try:
            bridge = self._ari.bridges.get(bridgeId=bridge_id)
        except ARINotFound:
            bridge = self._ari.bridges.createWithId(type='holding', bridgeId=bridge_id)

        if len(bridge.json['channels']) == 0:
            bridge.startMoh()

        channel = self._ari.channels.get(channelId=channel_id)
        channel.setChannelVar(variable='WAZO_SWITCHBOARD_QUEUE', value=switchboard_uuid)
        channel.setChannelVar(variable='WAZO_TENANT_UUID', value=tenant_uuid)
        channel.answer()
        bridge.addChannel(channel=channel_id)

        calls = self.queued_calls(tenant_uuid, switchboard_uuid)
        self._notifier.queued_calls(tenant_uuid, switchboard_uuid, calls)

    def answer_queued_call(self, tenant_uuid, switchboard_uuid, queued_call_id,
                           user_uuid, line_id=None):
        if not Switchboard(tenant_uuid, switchboard_uuid, self._confd).exists():
            raise NoSuchSwitchboard(switchboard_uuid)

        try:
            queued_channel = self._ari.channels.get(channelId=queued_call_id)
        except ARINotFound:
            raise NoSuchCall(queued_call_id)

        try:
            user = User(user_uuid, self._confd, tenant_uuid=tenant_uuid)
            if line_id:
                line = user.line(line_id)
            else:
                line = user.main_line()
            endpoint = line.interface_autoanswer()
        except InvalidUserUUID as e:
            raise NoSuchConfdUser(e.details['user_uuid'])

        caller_id = assemble_caller_id(
            queued_channel.json['caller']['name'],
            queued_channel.json['caller']['number']
        ).encode('utf-8')

        channel = self._ari.channels.originate(
            endpoint=endpoint,
            app=DEFAULT_APPLICATION_NAME,
            appArgs=['switchboard', 'switchboard_answer', tenant_uuid, switchboard_uuid, queued_call_id],
            callerId=caller_id,
            originator=queued_call_id,
            variables={'variables': AUTO_ANSWER_VARIABLES},
        )

        return channel.id

    def hold_call(self, tenant_uuid, switchboard_uuid, call_id):
        if not Switchboard(tenant_uuid, switchboard_uuid, self._confd).exists():
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
        channel_to_hold.setChannelVar(variable='WAZO_TENANT_UUID', value=tenant_uuid)

        held_calls = self.held_calls(tenant_uuid, switchboard_uuid)
        self._notifier.held_calls(tenant_uuid, switchboard_uuid, held_calls)

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

    def held_calls(self, tenant_uuid, switchboard_uuid):
        if not Switchboard(tenant_uuid, switchboard_uuid, self._confd).exists():
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

    def answer_held_call(self, tenant_uuid, switchboard_uuid, held_call_id,
                         user_uuid, line_id=None):
        if not Switchboard(tenant_uuid, switchboard_uuid, self._confd).exists():
            raise NoSuchSwitchboard(switchboard_uuid)

        try:
            held_channel = self._ari.channels.get(channelId=held_call_id)
        except ARINotFound:
            raise NoSuchCall(held_call_id)

        try:
            user = User(user_uuid, self._confd, tenant_uuid=tenant_uuid)
            if line_id:
                line = user.line(line_id)
            else:
                line = user.main_line()
            endpoint = line.interface_autoanswer()
        except InvalidUserUUID as e:
            raise NoSuchConfdUser(e.details['user_uuid'])

        caller_id = assemble_caller_id(
            held_channel.json['caller']['name'],
            held_channel.json['caller']['number'],
        ).encode('utf-8')

        channel = self._ari.channels.originate(
            endpoint=endpoint,
            app=DEFAULT_APPLICATION_NAME,
            appArgs=['switchboard', 'switchboard_unhold', tenant_uuid, switchboard_uuid, held_call_id],
            callerId=caller_id,
            variables={'variables': AUTO_ANSWER_VARIABLES},
        )

        return channel.id
