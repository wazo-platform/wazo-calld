# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo_ctid_ng.core.ari_ import APPLICATION_NAME

from .event import CallEvent
from .event import StartCallEvent
from .event import ConnectCallEvent
from .exceptions import InvalidConnectCallEvent
from .stat_sender import StatSender
from .state import state_factory
from .state import CallStateOnHook
from .state_persistor import ChannelCacheEntry
from .state_persistor import StatePersistor

logger = logging.getLogger(__name__)


class NullHandle(object):
    def close(self):
        pass


class CallsStasis(object):

    def __init__(self, ari_client, collectd, bus_publisher, services, xivo_uuid):
        self.ari = ari_client
        self.bus_publisher = bus_publisher
        self.collectd = collectd
        self.services = services
        self.stat_sender = StatSender(collectd)
        self.state_factory = state_factory
        self.state_factory.set_dependencies(ari_client, self.stat_sender)
        self.state_persistor = StatePersistor(ari_client)
        self.subscribe_all_channels_handle = NullHandle()
        self.xivo_uuid = xivo_uuid

    def subscribe(self):
        self.ari.on_channel_event('StasisStart', self.stasis_start)
        self.ari.on_channel_event('ChannelDestroyed', self.channel_destroyed)
        self.subscribe_all_channels_handle = self.ari.on_channel_event('StasisStart', self.subscribe_to_all_channel_events)

    def subscribe_to_all_channel_events(self, event_objects, event):
        self.subscribe_all_channels_handle.close()
        self.ari.applications.subscribe(applicationName=APPLICATION_NAME, eventSource='channel:')

    def stasis_start(self, event_objects, event):
        channel = event_objects['channel']
        if ConnectCallEvent.is_connect_event(event):
            self._stasis_start_connect(channel, event)
        else:
            self._stasis_start_new_call(channel, event)

    def _stasis_start_connect(self, channel, event):
        try:
            connect_event = ConnectCallEvent(channel, event, self.ari, self.state_persistor)
        except InvalidConnectCallEvent:
            logger.error('tried to connect call %s but no originator found', channel.id)
            return
        state_name = self.state_persistor.get(connect_event.originator_channel.id).state
        state = self.state_factory.make(state_name)
        new_state = state.connect(connect_event)
        self.state_persistor.upsert(channel.id, ChannelCacheEntry(app=connect_event.app,
                                                                  app_instance=connect_event.app_instance,
                                                                  state=new_state.name))

    def _stasis_start_new_call(self, channel, event):
        call_event = StartCallEvent(channel, event, self.state_persistor)
        state = self.state_factory.make(CallStateOnHook.name)
        new_state = state.ring(call_event)
        self.state_persistor.upsert(channel.id, ChannelCacheEntry(app=call_event.app,
                                                                  app_instance=call_event.app_instance,
                                                                  state=new_state.name))

    def channel_destroyed(self, channel, event):
        try:
            state_name = self.state_persistor.get(channel.id).state
        except KeyError:
            return

        state = self.state_factory.make(state_name)
        state.hangup(CallEvent(channel, event, self.state_persistor))

        self.state_persistor.remove(channel.id)
