# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import iso8601
import json
import logging

from requests.exceptions import HTTPError
from xivo_bus.collectd.calls.event import CallAbandonedCollectdEvent
from xivo_bus.collectd.calls.event import CallConnectCollectdEvent
from xivo_bus.collectd.calls.event import CallDurationCollectdEvent
from xivo_bus.collectd.calls.event import CallEndCollectdEvent
from xivo_bus.collectd.calls.event import CallStartCollectdEvent

from xivo_ctid_ng.core.ari_ import APPLICATION_NAME
from xivo_ctid_ng.core.ari_ import not_found

from .exceptions import InvalidCallEvent
from .exceptions import InvalidConnectCallEvent
from .exceptions import InvalidStartCallEvent

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
        state_name = self.state_persistor.get(channel.id).state

        state = self.state_factory.make(state_name)
        state.hangup(CallEvent(channel, event, self.state_persistor))

        self.state_persistor.remove(channel.id)


class ChannelCacheEntry(object):
    def __init__(self, app, app_instance, state):
        self.app = app
        self.app_instance = app_instance
        self.state = state

    def to_dict(self):
        return {'app': self.app,
                'app_instance': self.app_instance,
                'state': self.state}

    @classmethod
    def from_dict(cls, dict_):
        return cls(app=dict_['app'],
                   app_instance=dict_['app_instance'],
                   state=dict_['state'])


class StatePersistor(object):
    global_var_name = 'XIVO_CALLCONTROL'

    def __init__(self, ari):
        self._ari = ari

    def get(self, channel_id):
        return ChannelCacheEntry.from_dict(self._cache()[channel_id])

    def upsert(self, channel_id, entry):
        cache = self._cache()
        cache[channel_id] = entry.to_dict()
        self._set_cache(cache)

    def remove(self, channel_id):
        cache = self._cache()
        cache.pop(channel_id, None)
        self._set_cache(cache)

    def _cache(self):
        try:
            cache_str = self._ari.asterisk.getGlobalVar(variable=self.global_var_name)['value']
        except HTTPError as e:
            if not_found(e):
                return {}
            raise
        if not cache_str:
            return {}
        return json.loads(cache_str)

    def _set_cache(self, cache):
        self._ari.asterisk.setGlobalVar(variable=self.global_var_name,
                                        value=json.dumps(cache))


class CallEvent(object):

    def __init__(self, channel, event, state_persistor):
        self.channel = channel
        self._event = event
        self._state_persistor = state_persistor
        self.app, self.app_instance = self._get_app()

    def _get_app(self):
        try:
            cache_entry = self._state_persistor.get(self.channel.id)
        except KeyError:
            raise InvalidCallEvent()
        return cache_entry.app, cache_entry.app_instance

    def duration(self):
        start_time = self.channel.json['creationtime']
        start_datetime = iso8601.parse_date(start_time)

        end_time = self._event['timestamp']
        end_datetime = iso8601.parse_date(end_time)

        return (end_datetime - start_datetime).seconds


class StartCallEvent(CallEvent):

    def _get_app(self):
        if 'args' not in self._event:
            raise InvalidStartCallEvent()
        if len(self._event['args']) < 1:
            raise InvalidStartCallEvent()
        return self._event['application'], self._event['args'][0]


class ConnectCallEvent(StartCallEvent):

    def __init__(self, channel, event, ari, state_persistor):
        super(ConnectCallEvent, self).__init__(channel, event, state_persistor)
        originator_channel_id = self._originator_channel_id(event)
        try:
            self.originator_channel = ari.channels.get(channelId=originator_channel_id)
        except HTTPError as e:
            if not_found(e):
                raise InvalidConnectCallEvent()
            raise

    @classmethod
    def is_connect_event(self, event):
        if 'args' not in event:
            return False
        if len(event['args']) < 2:
            return False
        return event['args'][1] == 'dialed_from'

    def _originator_channel_id(self, event):
        if len(event['args']) < 3:
            raise InvalidConnectCallEvent()
        return event['args'][2]


class StateFactory(object):

    def __init__(self, ari=None, stat_sender=None):
        self._state_constructors = {}
        self._ari = ari
        self._stat_sender = stat_sender

    def set_dependencies(self, ari, stat_sender):
        self._ari = ari
        self._stat_sender = stat_sender

    def make(self, state_name):
        assert self._ari and self._stat_sender, 'StateFactory is not configured'
        return self._state_constructors[state_name](self._ari, self._stat_sender)

    def state(self, wrapped_class):
        self._state_constructors[wrapped_class.name] = wrapped_class
        return wrapped_class


state_factory = StateFactory()


class CallState(object):

    name = None

    def __init__(self, ari, stat_sender):
        self._ari = ari
        self._stat_sender = stat_sender

    def ring(self):
        pass

    def connect(self):
        pass

    def hangup(self):
        pass

    @classmethod
    def from_state(cls, other_state):
        return cls(other_state._ari,
                   other_state._stat_sender)


@state_factory.state
class CallStateRinging(CallState):

    name = 'ringing'

    def connect(self, call):
        self._bridge_connect_user(call)
        self._stat_sender.connect(call)
        return CallStateTalking.from_state(self)

    def hangup(self, call):
        self._stat_sender.end_call(call)
        self._stat_sender.duration(call)
        self._stat_sender.abandoned(call)
        return CallStateOnHook.from_state(self)

    def _bridge_connect_user(self, call):
        logger.debug('connecting originator %s with callee %s', call.originator_channel.id, call.channel.id)
        call.channel.answer()
        call.originator_channel.answer()
        bridge = self._ari.bridges.create(type='mixing')
        bridge.addChannel(channel=call.originator_channel.id)
        bridge.addChannel(channel=call.channel.id)


@state_factory.state
class CallStateTalking(CallState):

    name = 'talking'

    def hangup(self, call):
        self._stat_sender.end_call(call)
        self._stat_sender.duration(call)
        return CallStateOnHook.from_state(self)


@state_factory.state
class CallStateOnHook(CallState):

    name = 'on_hook'

    def ring(self, call):
        self._stat_sender.new_call(call)
        return CallStateRinging.from_state(self)


class StatSender(object):

    def __init__(self, collectd):
        self.collectd = collectd

    def new_call(self, call):
        logger.debug('sending stat for new call %s', call.channel.id)
        self.collectd.publish(CallStartCollectdEvent(call.app, call.app_instance))

    def abandoned(self, call):
        logger.debug('sending stat for abandoned call %s', call.channel.id)
        self.collectd.publish(CallAbandonedCollectdEvent(call.app, call.app_instance))

    def duration(self, call):
        logger.debug('sending stat for duration of call %s', call.channel.id)
        self.collectd.publish(CallDurationCollectdEvent(call.app, call.app_instance, call.duration()))

    def connect(self, call):
        logger.debug('sending stat for connecting call %s', call.channel.id)
        self.collectd.publish(CallConnectCollectdEvent(call.app, call.app_instance))

    def end_call(self, call):
        logger.debug('sending stat for ended call %s', call.channel.id)
        self.collectd.publish(CallEndCollectdEvent(call.app, call.app_instance))
