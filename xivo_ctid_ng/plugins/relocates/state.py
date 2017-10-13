# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo_ctid_ng.ari_ import APPLICATION_NAME

logger = logging.getLogger(__name__)


class StateFactory(object):

    def __init__(self, ari=None):
        self._state_constructors = {}
        self._ari = ari
        self._configured = False

    def set_dependencies(self, *dependencies):
        self._dependencies = dependencies
        self._configured = True

    def make(self, state_name):
        if not self._configured:
            raise RuntimeError('StateFactory is not configured')
        return self._state_constructors[state_name](*self._dependencies)

    def state(self, wrapped_class):
        self._state_constructors[wrapped_class.name] = wrapped_class
        return wrapped_class


state_factory = StateFactory()


class RelocateState(object):

    def __init__(self, ari, services, relocate_lock):
        self._ari = ari
        self._services = services
        self._relocate_lock = relocate_lock


@state_factory.state
class RelocateStateReady(RelocateState):

    name = 'ready'

    def initiate(self, relocate, destination):
        new_channel = self._ari.channels.originate(
            endpoint=destination.ari_endpoint(),
            app=APPLICATION_NAME,
            appArgs=['relocate', relocate.uuid, 'recipient'],
            originator=relocate.relocated_channel
        )

        relocate.recipient_channel = new_channel.id
        relocate.set_state('recipient_ring')


@state_factory.state
class RelocateStateRecipientRing(RelocateState):

    name = 'recipient_ring'

    def recipient_answered(self, relocate):
        bridge = self._ari.bridges.create(type='mixing', name='relocate:{}'.format(relocate.uuid))
        bridge.addChannel(channel=relocate.recipient_channel)
        bridge.addChannel(channel=relocate.relocated_channel)
        self._ari.channels.hangup(channelId=relocate.initiator_channel)

        relocate.set_state('ended')


@state_factory.state
class RelocateStateEnded(RelocateState):

    name = 'ended'

    def recipient_hangup(self, relocate):
        pass

    def initiator_hangup(self, relocate):
        pass

    def relocated_hangup(self, relocate):
        pass
