# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from ari.exceptions import ARINotFound

from xivo.caller_id import assemble_caller_id
from xivo_ctid_ng.core.ari_ import APPLICATION_NAME
from xivo_ctid_ng.helpers.confd import User

from .call import QueuedCall
from .confd import Switchboard
from .exceptions import NoSuchCall
from .exceptions import NoSuchSwitchboard

BRIDGE_QUEUE_ID = 'switchboard-{uuid}-queue'


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
        caller_id = assemble_caller_id(queued_channel.json['caller']['name'], queued_channel.json['caller']['number']).encode('utf-8')

        channel = self._ari.channels.originate(endpoint=endpoint,
                                               app=APPLICATION_NAME,
                                               appArgs=['switchboard_answer', switchboard_uuid, queued_call_id],
                                               callerId=caller_id)

        return channel.id
