# Copyright 2016-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from wazo_calld.ari_ import DEFAULT_APPLICATION_NAME
from xivo_bus.resources.common.event import ArbitraryEvent

from .event import (
    CallEvent,
    ConnectCallEvent,
    StartCallEvent,
)
from .exceptions import InvalidConnectCallEvent
from .schemas import call_schema
from .stat_sender import StatSender
from .state import (
    CallStateOnHook,
    state_factory,
)
from .state_persistor import (
    ChannelCacheEntry,
    StatePersistor,
)

logger = logging.getLogger(__name__)


class CallsStasis:

    def __init__(self, ari, collectd, bus_publisher, services, xivo_uuid, amid_client):
        self.ari = ari.client
        self._core_ari = ari
        self.bus_publisher = bus_publisher
        self.collectd = collectd
        self.services = services
        self.stat_sender = StatSender(collectd)
        self.state_factory = state_factory
        self.state_factory.set_dependencies(self.ari, self.stat_sender)
        self.state_persistor = StatePersistor(self.ari)
        self.xivo_uuid = xivo_uuid
        self.ami = amid_client

    def initialize(self):
        self._subscribe()
        self._core_ari.register_application(DEFAULT_APPLICATION_NAME)

    def _subscribe(self):
        self.ari.on_channel_event('StasisStart', self.stasis_start)
        self.ari.on_channel_event('ChannelDestroyed', self.channel_destroyed)
        self.ari.on_channel_event('ChannelDestroyed', self.relay_channel_hung_up)
        self.ari.on_application_registered(DEFAULT_APPLICATION_NAME, self.subscribe_to_all_channel_events)
        self.ari.on_application_deregistered(DEFAULT_APPLICATION_NAME, self.unsubscribe_from_all_channel_events)

    def subscribe_to_all_channel_events(self):
        self.ari.applications.subscribe(applicationName=DEFAULT_APPLICATION_NAME, eventSource='channel:')

    def unsubscribe_from_all_channel_events(self):
        self.ari.applications.unsubscribe(
            applicationName=DEFAULT_APPLICATION_NAME,
            eventSource='channel:__AST_CHANNEL_ALL_TOPIC',
        )

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

    def relay_channel_hung_up(self, channel, event):
        channel_id = channel.id
        channel_info = event['channel']
        name = channel_info.get('name')
        if name.startswith('Local/'):
            logger.debug('Ignoring local channel hangup: %s', channel_id)
            return
        logger.debug('Relaying to bus: channel %s ended', channel_id)
        call = self.services.make_call_from_stasis_event(event)
        bus_event = ArbitraryEvent(
            name='call_ended',
            body=call_schema.dump(call),
            required_acl='events.calls.{}'.format(call.user_uuid),
        )
        bus_event.routing_key = 'calls.call.ended'
        self.bus_publisher.publish(bus_event, headers={'user_uuid:{uuid}'.format(uuid=call.user_uuid): True})
