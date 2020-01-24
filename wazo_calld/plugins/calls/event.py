# Copyright 2016-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import iso8601

from ari.exceptions import ARINotFound

from .exceptions import InvalidCallEvent
from .exceptions import InvalidConnectCallEvent
from .exceptions import InvalidStartCallEvent


class CallEvent:

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
        first_arg = self._event['args'][0] if self._event['args'] else None
        return self._event['application'], first_arg


class ConnectCallEvent(StartCallEvent):

    def __init__(self, channel, event, ari, state_persistor):
        super().__init__(channel, event, state_persistor)
        originator_channel_id = self._originator_channel_id(event)
        try:
            self.originator_channel = ari.channels.get(channelId=originator_channel_id)
        except ARINotFound:
            raise InvalidConnectCallEvent()

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


class _BaseEvent:

    required_acl = 'events.{}'

    def marshal(self):
        return self._body


class _BaseCallItemEvent(_BaseEvent):

    def __init__(self, call):
        self.routing_key = self.routing_key.format(call['id'])
        self.required_acl = self.required_acl.format(self.routing_key)
        self._body = {
            'call': call
        }


class CallUpdated(_BaseCallItemEvent):
    name = 'call_updated'
    routing_key = 'calls.{}.updated'
