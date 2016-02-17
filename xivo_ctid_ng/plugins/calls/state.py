# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import logging

logger = logging.getLogger(__name__)


class StateFactory(object):

    def __init__(self, ari=None, stat_sender=None):
        self._state_constructors = {}
        self._ari = ari
        self._stat_sender = stat_sender

    def set_dependencies(self, ari, stat_sender):
        self._ari = ari
        self._stat_sender = stat_sender

    def make(self, state_name):
        if not self._ari or not self._stat_sender:
            raise RuntimeError('StateFactory is not configured')
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
