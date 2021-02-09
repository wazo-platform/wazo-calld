# Copyright 2015-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import time
import json

from ari.exceptions import ARINotFound, ARINotInStasis

from .exceptions import (
    NotEnoughChannels,
    TooManyChannels,
)

logger = logging.getLogger(__name__)

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


def set_channel_var_sync(channel, var, value, bypass_stasis=False):
    # TODO remove this when Asterisk gets fixed to set var synchronously
    def get_value():
        try:
            return channel.getChannelVar(variable=var)['value']
        except ARINotFound as e:
            if e.original_error.response.reason == 'Variable Not Found':
                return None
            raise

    channel.setChannelVar(variable=var, value=value, bypassStasis=bypass_stasis)
    for _ in range(20):
        if get_value() == value:
            return

        logger.debug('waiting for a setvar to complete')
        time.sleep(0.01)

    raise Exception('failed to set channel variable {}={}'.format(var, value))


def set_channel_id_var_sync(ari, channel_id, var, value, bypass_stasis=False):
    # TODO remove this when Asterisk gets fixed to set var synchronously
    def get_value():
        try:
            return ari.channels.getChannelVar(channelId=channel_id, variable=var)['value']
        except ARINotFound as e:
            if e.original_error.response.reason == 'Variable Not Found':
                return None
            raise

    ari.channels.setChannelVar(
        channelId=channel_id,
        variable=var,
        value=value,
        bypassStasis=bypass_stasis,
    )
    for _ in range(20):
        if get_value() == value:
            return

        logger.debug('waiting for a setvar to complete')
        time.sleep(0.01)

    raise Exception('failed to set channel variable {}={}'.format(var, value))


class GlobalVariableAdapter:

    def __init__(self, ari_client):
        self._ari = ari_client

    def get(self, variable, default=None):
        try:
            return self._ari.asterisk.getGlobalVar(variable=variable)['value']
        except ARINotFound:
            if default is None:
                raise KeyError(variable)
            return default

    def set(self, variable, value):
        self._ari.asterisk.setGlobalVar(variable=variable, value=value)

    def unset(self, variable):
        self._ari.asterisk.setGlobalVar(variable=variable, value='')


class GlobalVariableJsonAdapter:

    def __init__(self, global_variables):
        self._global_variables = global_variables

    def get(self, variable, default=None):
        value = self._global_variables.get(variable)
        if not value:
            if default is None:
                raise KeyError(variable)
            return default
        return json.loads(value)

    def set(self, variable, value):
        self._global_variables.set(variable, json.dumps(value))

    def unset(self, variable):
        self._global_variables.unset(variable)


class GlobalVariableNameDecorator:

    def __init__(self, global_variables, variable_name_format):
        self._global_variables = global_variables
        self._format = variable_name_format

    def get(self, variable, default=None):
        return self._global_variables.get(self._format.format(variable), default)

    def set(self, variable, value):
        return self._global_variables.set(self._format.format(variable), value)

    def unset(self, variable):
        return self._global_variables.unset(self._format.format(variable))


class GlobalVariableConstantNameAdapter:

    def __init__(self, global_variables, variable_name):
        self._global_variables = global_variables
        self._variable = variable_name

    def get(self, default=None):
        return self._global_variables.get(self._variable, default)

    def set(self, value):
        return self._global_variables.set(self._variable, value)

    def unset(self):
        return self._global_variables.unset(self._variable)


class Channel:

    def __init__(self, channel_id, ari):
        self.id = channel_id
        self._ari = ari

    def __str__(self):
        return self.id

    def connected_channels(self):
        channel_ids = set(sum((bridge.json['channels'] for bridge in self._ari.bridges.list()
                               if self.id in bridge.json['channels']), list()))
        try:
            channel_ids.remove(self.id)
        except KeyError:
            pass
        return {Channel(channel_id, self._ari) for channel_id in channel_ids}

    def only_connected_channel(self):
        connected_channels = self.connected_channels()
        if len(connected_channels) > 1:
            raise TooManyChannels(channel.id for channel in connected_channels)
        try:
            channel_id = connected_channels.pop().id
        except KeyError:
            raise NotEnoughChannels()
        return Channel(channel_id, self._ari)

    def user(self, default=None):
        if self.is_local():
            try:
                uuid = self._get_var('WAZO_DEREFERENCED_USERUUID')
            except ARINotFound:
                return default
            return uuid

        try:
            uuid = self._get_var('XIVO_USERUUID')
            return uuid
        except ARINotFound:
            return default

    def exists(self):
        try:
            self._ari.channels.get(channelId=self.id)
            return True
        except ARINotFound:
            return False

    def is_local(self):
        try:
            channel = self._ari.channels.get(channelId=self.id)
        except ARINotFound:
            return False

        return channel.json['name'].startswith('Local/')

    def is_caller(self):
        try:
            user_outgoing_call = self._get_var('WAZO_USER_OUTGOING_CALL')
            return user_outgoing_call == 'true'
        except ARINotFound:
            pass

        try:
            direction = self._get_var('WAZO_CHANNEL_DIRECTION')
            return direction == 'to-wazo'
        except ARINotFound:
            pass

        return False

    def is_in_stasis(self):
        try:
            self._ari.channels.setChannelVar(channelId=self.id, variable='WAZO_TEST_STASIS')
            return True
        except ARINotInStasis:
            return False

    def is_sip(self):
        try:
            return self._get_var('CHANNEL(channeltype)') == 'PJSIP'
        except ARINotFound:
            return False

    def dialed_extension(self):
        try:
            channel = self._ari.channels.get(channelId=self.id)
        except ARINotFound:
            return

        try:
            return channel.getChannelVar(variable='XIVO_BASE_EXTEN')['value']
        except ARINotFound:
            return channel.json['dialplan']['exten']

    def on_hold(self):
        try:
            on_hold = self._get_var('XIVO_ON_HOLD')
            return on_hold == '1'
        except ARINotFound:
            return False

    def muted(self):
        try:
            muted = self._get_var('WAZO_CALL_MUTED')
            return muted == '1'
        except ARINotFound:
            return False

    def is_progress(self):
        try:
            progress = self._get_var('WAZO_CALL_PROGRESS')
            return progress == '1'
        except ARINotFound:
            return False

    def sip_call_id(self):
        if not self.is_sip():
            return
        return self.sip_call_id_unsafe()

    def sip_call_id_unsafe(self):
        '''This method expects a SIP channel'''
        try:
            return self._get_var('CHANNEL(pjsip,call-id)')
        except ARINotFound:
            return

    def line_id(self):
        try:
            return int(self._get_var('WAZO_LINE_ID'))
        except ARINotFound:
            return
        except ValueError:
            logger.error('Channel %s: Malformed WAZO_LINE_ID=%s', self.id, self._get_var('WAZO_LINE_ID'))
            return

    def wait_until_in_stasis(self, retry=20, delay=0.1):
        for _ in range(retry):
            if self.is_in_stasis():
                return
            time.sleep(delay)

        raise Exception('call failed to enter stasis')

    def _get_var(self, var):
        return self._ari.channels.getChannelVar(channelId=self.id, variable=var)['value']


class Bridge:

    def __init__(self, bridge_id, ari):
        self.id = bridge_id
        self._ari = ari
        self.global_variables = GlobalVariableNameDecorator(
            GlobalVariableAdapter(self._ari),
            'WAZO_BRIDGE_{bridge_id}_VARIABLE_{{}}'.format(bridge_id=self.id)
        )

    def has_lone_channel(self):
        try:
            bridge = self._ari.bridges.get(bridgeId=self.id)
        except ARINotFound:
            return False

        return len(bridge.json['channels']) == 1

    def is_empty(self):
        try:
            bridge = self._ari.bridges.get(bridgeId=self.id)
        except ARINotFound:
            return False

        return len(bridge.json['channels']) == 0

    def hangup_all(self):
        try:
            bridge = self._ari.bridges.get(bridgeId=self.id)
        except ARINotFound:
            return

        for channel_id in bridge.json['channels']:
            try:
                self._ari.channels.hangup(channelId=channel_id)
            except ARINotFound:
                pass

    def valid_user_uuids(self):
        try:
            bridge = self._ari.bridges.get(bridgeId=self.id)
        except ARINotFound:
            return set()

        return set(Channel(channel_id, self._ari).user() for channel_id in bridge.json['channels'])

    def exists(self):
        try:
            self._ari.bridges.get(bridgeId=self.id)
        except ARINotFound:
            return False
        return True


class BridgeSnapshot(Bridge):
    def __init__(self, snapshot, ari):
        self._snapshot = snapshot
        super().__init__(snapshot['id'], ari)

    def valid_user_uuids(self):
        return set(Channel(channel_id, self._ari).user() for channel_id in self._snapshot['channels'])
