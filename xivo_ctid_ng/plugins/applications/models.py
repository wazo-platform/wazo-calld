# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from uuid import uuid4
from requests import HTTPError

from ari.exceptions import ARINotFound
from xivo_ctid_ng.helpers.ari_ import Channel as _ChannelHelper

from .exceptions import (
    NoSuchCall,
    NoSuchSnoop,
)


class ApplicationCall(object):

    def __init__(self, id_):
        self.id_ = id_
        self.moh_uuid = None
        self.muted = False


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

        try:
            call.muted = channel.getChannelVar(variable='WAZO_CALL_MUTED').get('value') == '1'
        except ARINotFound:
            call.muted = False

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


class _Snoop(object):

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
        self._bridge = ari.bridges.createWithId(
            bridgeId=self.uuid,
            name=self.bridge_name,
            type='mixing',
        )

        try:
            self._bridge.addChannel(channel=self.snooping_call_id)
        except HTTPError as e:
            response = getattr(e, 'response', None)
            status_code = getattr(response, 'status_code', None)
            if status_code == 400:
                raise NoSuchCall(self.snooping_call_id, status_code=400)
            raise

    def update_snoop_channel(self, snoop_channel):
        old_snoop_channel = self._snoop_channel
        self._snoop_channel = snoop_channel
        self._bridge.addChannel(channel=self._snoop_channel.id)
        if old_snoop_channel:
            old_snoop_channel.hangup()

    def new_snoop_channel(self, ari, whisper_mode):
        try:
            snoop_channel = ari.channels.snoopChannel(
                channelId=self.snooped_call_id,
                spy='both',
                whisper=whisper_mode,
                app=self.application['name'],
            )
        except ARINotFound:
            raise NoSuchCall(self.snooped_call_id)

        snoop_channel.setChannelVar(
            variable=self._whisper_mode_chan_var,
            value=whisper_mode,
        )
        snoop_channel.setChannelVar(
            variable=self._snooped_call_id_chan_var,
            value=self.snooped_call_id
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
            return None

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
        return snoop_channel.getChannelVar(variable=cls._snooped_call_id_chan_var)['value']

    @classmethod
    def get_whisper_mode(cls, snoop_channel):
        return snoop_channel.getChannelVar(variable=cls._whisper_mode_chan_var)['value']


class SnoopHelper(object):

    def __init__(self, ari):
        self._ari = ari

    def create(self, application, snooped_call_id, snooping_call_id, whisper_mode):
        self.validate_ownership(application, snooped_call_id, snooping_call_id)

        snoop = _Snoop(application, snooped_call_id, snooping_call_id)
        try:
            snoop.create_bridge(self._ari)
            snoop_channel = snoop.new_snoop_channel(self._ari, whisper_mode)
            snoop.update_snoop_channel(snoop_channel)
        except Exception:
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
        for snoop_bridge in self._find_snoop_channels(application):
            if snoop_bridge.id != uuid:
                continue

            snoop = _Snoop.from_bridge(self._ari, application, snoop_bridge)
            if snoop:
                return snoop

        raise NoSuchSnoop(snoop_uuid)

    def list_(self, application):
        for snoop_bridge in self._find_snoop_channels(application):
            yield _Snoop.from_bridge(self._ari, application, snoop_bridge)

    def _find_snoop_channels(self, application):
        bridge_name = _Snoop.bridge_name_tpl.format(application['uuid'])
        for bridge in self._ari.bridges.list():
            if bridge.json['name'] == bridge_name:
                yield bridge

    def validate_ownership(self, application, snooped_call_id, snooping_call_id=None):
        if snooped_call_id not in application['channel_ids']:
            raise NoSuchCall(snooped_call_id, status_code=404)
        if snooping_call_id and snooping_call_id not in application['channel_ids']:
            raise NoSuchCall(snooping_call_id, status_code=400)
