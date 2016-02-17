# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import iso8601

from requests.exceptions import HTTPError

from xivo_ctid_ng.core.ari_ import not_found

from .exceptions import InvalidCallEvent
from .exceptions import InvalidConnectCallEvent
from .exceptions import InvalidStartCallEvent


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
