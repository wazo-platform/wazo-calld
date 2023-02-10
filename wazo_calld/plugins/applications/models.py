# Copyright 2018-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from uuid import uuid4
from requests import HTTPError

from ari.exceptions import ARINotFound
from wazo_calld.plugin_helpers.ari_ import Channel as _ChannelHelper

from .exceptions import (
    NoSuchCall,
    NoSuchSnoop,
)

logger = logging.getLogger(__name__)


class InvalidSnoopBridge(Exception):
    def __init__(self, bridge_id):
        self.bridge_id = bridge_id
        super().__init__(
            'Invalid snoop bridge id "{bridge_id}"'.format(bridge_id=bridge_id)
        )


class ApplicationCall:
    def __init__(self, id_):
        self.id_ = id_
        self.moh_uuid = None
        self.muted = False
        self.user_uuid = None
        self.tenant_uuid = None


class ApplicationNode:
    def __init__(self, uuid):
        self.uuid = uuid
        self.calls = []


class CallFormatter:
    def __init__(self, application, ari=None):
        self._application = application
        self._ari = ari
        self._snoop_list = None

    def from_channel(self, channel, variables=None, node_uuid=None):
        call = ApplicationCall(channel.id)
        call.creation_time = channel.json['creationtime']
        call.status = channel.json['state']
        call.caller_id_name = channel.json['caller']['name']
        call.caller_id_number = channel.json['caller']['number']
        call.snoops = self._get_snoops(channel)

        if node_uuid:
            call.node_uuid = node_uuid

        if self._ari is not None:
            channel_helper = _ChannelHelper(channel.id, self._ari)
            call.on_hold = channel_helper.on_hold()
            call.is_caller = channel_helper.is_caller()
            call.dialed_extension = channel_helper.dialed_extension()
            try:
                call.moh_uuid = (
                    channel.getChannelVar(variable='WAZO_MOH_UUID').get('value') or None
                )
            except ARINotFound:
                call.moh_uuid = None

            try:
                call.user_uuid = channel.getChannelVar(variable='XIVO_USERUUID').get(
                    'value'
                )
            except ARINotFound:
                call.user_uuid = None

            try:
                call.tenant_uuid = channel.getChannelVar(
                    variable='WAZO_TENANT_UUID'
                ).get('value')
            except ARINotFound:
                call.tenant_uuid = None

            try:
                call.muted = (
                    channel.getChannelVar(variable='WAZO_CALL_MUTED').get('value')
                    == '1'
                )
            except ARINotFound:
                call.muted = False

            call.node_uuid = getattr(call, 'node_uuid', None)
            for bridge in self._ari.bridges.list():
                if channel.id in bridge.json['channels']:
                    call.node_uuid = bridge.id
                    break

            if call.status == 'Ring' and channel_helper.is_progress():
                call.status = 'Progress'

        if variables is not None:
            call.variables = variables

        return call

    def _get_snoops(self, channel):
        if self._snoop_list is None:
            if not self._ari:
                return {}

            snoop_helper = SnoopHelper(self._ari)
            self._snoop_list = snoop_helper.list_(self._application)

        result = {}
        for snoop in self._snoop_list:
            if channel.id == snoop.snooped_call_id:
                result[snoop.uuid] = {
                    'uuid': snoop.uuid,
                    'role': 'snooped',
                }
            elif channel.id == snoop.snooping_call_id:
                result[snoop.uuid] = {
                    'uuid': snoop.uuid,
                    'role': 'snooper',
                }
        return result


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


class _Snoop:
    bridge_name_tpl = 'wazo-app-snoop-{}'
    _snooped_call_id_chan_var = 'WAZO_SNOOPED_CALL_ID'
    _whisper_mode_chan_var = 'WAZO_SNOOP_WHISPER_MODE'

    def __init__(self, application, snooped_call_id, snooping_call_id, **kwargs):
        self.uuid = kwargs.get('uuid') or str(uuid4())
        self.application = application
        self.snooped_call_id = snooped_call_id
        self.snooping_call_id = snooping_call_id
        self.bridge_name = self.bridge_name_tpl.format(application['uuid'])
        self.whisper_mode = kwargs.get('whisper_mode')
        self._bridge = kwargs.get('bridge')
        self._snoop_channel = kwargs.get('snoop_channel')

    def create_bridge(self, ari):
        logger.debug(
            'creating a new snoop bridge for snoop %s %s', self.uuid, self.bridge_name
        )
        self._bridge = ari.bridges.createWithId(
            bridgeId=self.uuid,
            name=self.bridge_name,
            type='mixing',
        )

        try:
            logger.debug(
                'adding the snooping call to the bridge %s %s',
                self.uuid,
                self.snooping_call_id,
            )
            self._bridge.addChannel(channel=self.snooping_call_id)
        except HTTPError as e:
            response = getattr(e, 'response', None)
            status_code = getattr(response, 'status_code', None)
            logger.debug(
                'failed to add the channel to the snooping bridge %s', status_code
            )
            if status_code == 400:
                raise NoSuchCall(self.snooping_call_id, status_code=400)
            raise

    def update_snoop_channel(self, snoop_channel):
        logger.debug(
            'updating the snoop channel from %s to %s',
            self._snoop_channel,
            snoop_channel,
        )
        old_snoop_channel = self._snoop_channel
        self._snoop_channel = snoop_channel
        logger.debug('adding the new snoop channel %s', self._snoop_channel)
        self._bridge.addChannel(channel=self._snoop_channel.id)
        if old_snoop_channel:
            old_snoop_channel.hangup()

    def new_snoop_channel(self, ari, whisper_mode):
        logger.debug('Creating new snoop channel')
        try:
            snoop_channel = ari.channels.snoopChannel(
                channelId=self.snooped_call_id,
                spy='both',
                whisper=whisper_mode,
                app=self.application['name'],
            )
        except ARINotFound:
            raise NoSuchCall(self.snooped_call_id)

        _ChannelHelper(snoop_channel.id, ari).wait_until_in_stasis()

        snoop_channel.setChannelVar(
            variable=self._whisper_mode_chan_var,
            value=whisper_mode,
        )
        snoop_channel.setChannelVar(
            variable=self._snooped_call_id_chan_var,
            value=self.snooped_call_id,
        )
        self.whisper_mode = whisper_mode

        return snoop_channel

    def destroy(self):
        if self._bridge:
            try:
                self._bridge.destroy()
            except ARINotFound:
                pass

        if self._snoop_channel:
            try:
                self._snoop_channel.hangup()
            except ARINotFound:
                pass

    @classmethod
    def from_bridge(cls, ari, application, bridge):
        snoop_channel = None

        for channel_id in bridge.json['channels']:
            try:
                channel = ari.channels.get(channelId=channel_id)
                if channel.json['name'].startswith('Snoop/'):
                    snoop_channel = channel
                else:
                    snooping_call_id = channel_id
            except ARINotFound:
                continue

        if not snoop_channel:
            raise InvalidSnoopBridge(bridge.id)

        snooped_call_id = cls.get_snooped_call_id(snoop_channel)
        whisper_mode = cls.get_whisper_mode(snoop_channel)
        snoop = cls(
            application,
            snooped_call_id,
            snooping_call_id,
            whisper_mode=whisper_mode,
            uuid=bridge.id,
            bridge=bridge,
            snoop_channel=snoop_channel,
        )
        return snoop

    @classmethod
    def get_snooped_call_id(cls, snoop_channel):
        return snoop_channel.getChannelVar(variable=cls._snooped_call_id_chan_var)[
            'value'
        ]

    @classmethod
    def get_whisper_mode(cls, snoop_channel):
        return snoop_channel.getChannelVar(variable=cls._whisper_mode_chan_var)['value']


class SnoopHelper:
    def __init__(self, ari):
        self._ari = ari

    def create(self, application, snooped_call_id, snooping_call_id, whisper_mode):
        self.validate_ownership(application, snooped_call_id, snooping_call_id)

        snoop = _Snoop(application, snooped_call_id, snooping_call_id)
        try:
            snoop.create_bridge(self._ari)
            snoop_channel = snoop.new_snoop_channel(self._ari, whisper_mode)
            snoop.update_snoop_channel(snoop_channel)
        except Exception as e:
            logger.debug('Error while creating the snoop bridge, destroying it. %s', e)
            snoop.destroy()
            raise
        return snoop

    def delete(self, application, snoop_uuid):
        snoop = self.get(application, snoop_uuid)
        snoop.destroy()

    def edit(self, application, snoop_uuid, whisper_mode):
        snoop = self.get(application, snoop_uuid)
        self.validate_ownership(application, snoop.snooped_call_id)

        snoop_channel = snoop.new_snoop_channel(self._ari, whisper_mode)
        snoop.update_snoop_channel(snoop_channel)
        return snoop

    def get(self, application, snoop_uuid):
        uuid = str(snoop_uuid)
        for snoop_bridge in self._snoop_bridges(application):
            if snoop_bridge.id != uuid:
                continue

            try:
                return _Snoop.from_bridge(self._ari, application, snoop_bridge)
            except InvalidSnoopBridge:
                pass

        raise NoSuchSnoop(snoop_uuid)

    def list_(self, application):
        result = []
        for snoop_bridge in self._snoop_bridges(application):
            try:
                snoop = _Snoop.from_bridge(self._ari, application, snoop_bridge)
            except InvalidSnoopBridge:
                pass
            else:
                result.append(snoop)
        return result

    def _snoop_bridges(self, application):
        bridge_name = _Snoop.bridge_name_tpl.format(application['uuid'])
        for bridge in self._ari.bridges.list():
            if bridge.json['name'] == bridge_name:
                yield bridge

    def validate_ownership(self, application, snooped_call_id, snooping_call_id=None):
        if snooped_call_id not in application['channel_ids']:
            raise NoSuchCall(snooped_call_id, status_code=404)
        if snooping_call_id and snooping_call_id not in application['channel_ids']:
            raise NoSuchCall(snooping_call_id, status_code=400)
