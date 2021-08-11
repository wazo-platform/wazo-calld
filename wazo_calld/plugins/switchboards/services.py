# Copyright 2017-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import threading

from ari.exceptions import ARINotFound

from xivo import dialaction
from xivo.caller_id import assemble_caller_id
from xivo.mallow.switchboard import SwitchboardFallbackSchema
from wazo_calld.ari_ import DEFAULT_APPLICATION_NAME
from wazo_calld.plugin_helpers.ari_ import AUTO_ANSWER_VARIABLES
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

logger = logging.getLogger(__name__)
switchboard_fallback_schema = SwitchboardFallbackSchema()


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
            moh_class = Switchboard(tenant_uuid, switchboard_uuid, self._confd).queue_moh()
            if moh_class:
                bridge.startMoh(mohClass=moh_class)
            else:
                bridge.startMoh()

        channel = self._ari.channels.get(channelId=channel_id)
        channel.setChannelVar(variable='WAZO_SWITCHBOARD_QUEUE', value=switchboard_uuid)
        channel.setChannelVar(variable='WAZO_TENANT_UUID', value=tenant_uuid)
        channel.answer()
        bridge.addChannel(channel=channel_id)

        calls = self.queued_calls(tenant_uuid, switchboard_uuid)
        self._notifier.queued_calls(tenant_uuid, switchboard_uuid, calls)

        noanswer_timeout = Switchboard(tenant_uuid, switchboard_uuid, self._confd).timeout()
        if not noanswer_timeout:
            logger.debug('Switchboard %s: ignoring no answer timeout = %s', switchboard_uuid, noanswer_timeout)
            return

        noanswer_fallback = self._confd.switchboards.relations(switchboard_uuid).list_fallbacks()['noanswer_destination']
        if not noanswer_fallback:
            logger.debug('Switchboard %s: ignoring no answer timeout because there is no fallback', switchboard_uuid)
            return

        logger.debug('Switchboard %s: starting no answer timeout for call %s after %s seconds', switchboard_uuid, channel_id, noanswer_timeout)
        timer = threading.Timer(noanswer_timeout, self.on_queued_call_noanswer_timeout, args=(tenant_uuid, switchboard_uuid, channel_id))
        timer.start()

    def on_queued_call_noanswer_timeout(self, tenant_uuid, switchboard_uuid, call_id):
        logger.debug('Switchboard %s: triggered no answer timeout for call %s', switchboard_uuid, call_id)

        fallbacks_confd = self._confd.switchboards.relations(switchboard_uuid).list_fallbacks()
        noanswer_destination_dialplan = switchboard_fallback_schema.load(fallbacks_confd)['noanswer']
        action = dialaction.action(
            noanswer_destination_dialplan['type'],
            noanswer_destination_dialplan['subtype']
        )
        try:
            self._ari.channels.setChannelVar(
                channelId=call_id,
                variable='XIVO_FWD_TYPE',
                value='SWITCHBOARD_NOANSWER'
            )
            self._ari.channels.setChannelVar(
                channelId=call_id,
                variable='XIVO_FWD_SWITCHBOARD_NOANSWER_ACTION',
                value=action
            )
            if noanswer_destination_dialplan.get('actionarg1'):
                self._ari.channels.setChannelVar(
                    channelId=call_id,
                    variable='XIVO_FWD_SWITCHBOARD_NOANSWER_ACTIONARG1',
                    value=noanswer_destination_dialplan['actionarg1']
                )
            if noanswer_destination_dialplan.get('actionarg2'):
                self._ari.channels.setChannelVar(
                    channelId=call_id,
                    variable='XIVO_FWD_SWITCHBOARD_NOANSWER_ACTIONARG2',
                    value=noanswer_destination_dialplan['actionarg2']
                )
            self._ari.channels.continueInDialplan(
                channelId=call_id,
                context='switchboard',
                extension='forward',
                priority='1'
            )
        except ARINotFound:
            logger.debug('%s: no such queued call in switchboard %s', call_id, switchboard_uuid)
        except Exception as e:
            logger.exception(
                'switcboard %s: Unexpected error on no answer timeout for call %s: %s',
                switchboard_uuid, call_id, e
            )

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
        if hold_bridge_id in [bridge.id for bridge in previous_bridges]:
            logger.debug('call %s already on hold in switchboard %s, nothing to do', call_id, switchboard_uuid)
            return

        try:
            hold_bridge = self._ari.bridges.get(bridgeId=hold_bridge_id)
        except ARINotFound:
            hold_bridge = self._ari.bridges.createWithId(type='holding', bridgeId=hold_bridge_id)

        if len(hold_bridge.json['channels']) == 0:
            moh_class = Switchboard(tenant_uuid, switchboard_uuid, self._confd).hold_moh()
            if moh_class:
                hold_bridge.startMoh(mohClass=moh_class)
            else:
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
