# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from xivo_ctid_ng.ari_ import APPLICATION_NAME

logger = logging.getLogger(__name__)
state_index = {}


def state(wrapped):
    state_index[wrapped.name] = wrapped
    return wrapped


class StateFactory(object):
    def __init__(self, index, ari):
        self._index = index
        self._state_args = [ari]

    def make(self, name):
        return self._index[name](*self._state_args)


class RelocateState(object):

    def __init__(self, ari):
        self._ari = ari


@state
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


@state
class RelocateStateRecipientRing(RelocateState):

    name = 'recipient_ring'

    def recipient_answered(self, relocate):
        bridge = self._ari.bridges.create(type='mixing', name='relocate:{}'.format(relocate.uuid))
        bridge.addChannel(channel=relocate.recipient_channel)
        bridge.addChannel(channel=relocate.relocated_channel)
        self._ari.channels.hangup(channelId=relocate.initiator_channel)

        relocate.set_state('ended')


@state
class RelocateStateEnded(RelocateState):

    name = 'ended'

    def recipient_hangup(self, relocate):
        pass

    def initiator_hangup(self, relocate):
        pass

    def relocated_hangup(self, relocate):
        pass
