# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging


from xivo_ctid_ng.ari_ import APPLICATION_NAME
from xivo_ctid_ng.exceptions import XiVOAmidError
from xivo_ctid_ng.helpers import ami
from xivo_ctid_ng.helpers.ari_ import Channel

from .exceptions import RelocateCompletionError

logger = logging.getLogger(__name__)
state_index = {}


def state(wrapped):
    state_index[wrapped.name] = wrapped
    return wrapped


class RelocateCompleter(object):

    def __init__(self, amid, ari):
        self._amid = amid
        self._ari = ari

    def bridge(self, relocate):
        bridge = self._ari.bridges.create(type='mixing', name='relocate:{}'.format(relocate.uuid))
        bridge.addChannel(channel=relocate.recipient_channel)
        bridge.addChannel(channel=relocate.relocated_channel)
        relocate.events.publish('completed', relocate)

    def move_to_stasis(self, relocate):
        self._ari.channels.setChannelVar(channelId=relocate.relocated_channel,
                                         variable='WAZO_RELOCATE_UUID',
                                         value=relocate.uuid,
                                         bypassStasis=True)
        try:
            ami.redirect(self._amid,
                         relocate.relocated_channel,
                         context='convert_to_stasis',
                         exten='relocate')
            relocate.events.publish('completed', relocate)
        except XiVOAmidError as e:
            logger.exception('xivo-amid error: %s', e.__dict__)


class StateFactory(object):
    def __init__(self, index, amid, ari):
        self._index = index
        self._state_args = [amid, ari]

    def make(self, name):
        return self._index[name](*self._state_args)


class RelocateState(object):

    def __init__(self, amid, ari):
        self._amid = amid
        self._ari = ari


@state
class RelocateStateReady(RelocateState):

    name = 'ready'

    def initiate(self, relocate, destination):
        new_channel = self._ari.channels.originate(
            endpoint=destination.ari_endpoint(),
            app=APPLICATION_NAME,
            appArgs=['relocate', relocate.uuid, 'recipient'],
            originator=relocate.relocated_channel,
            variables={'variables': relocate.recipient_variables},
            timeout=relocate.timeout,
        )

        relocate.recipient_channel = new_channel.id
        relocate.set_state('recipient_ring')
        relocate.events.publish('initiated', relocate)


@state
class RelocateStateRecipientRing(RelocateState):

    name = 'recipient_ring'

    def relocated_hangup(self, relocate):
        self._ari.channels.hangup(channelId=relocate.recipient_channel)
        relocate.set_state('ended')

    def initiator_hangup(self, relocate):
        self._ari.channels.hangup(channelId=relocate.recipient_channel)
        relocate.set_state('ended')

    def recipient_hangup(self, relocate):
        relocate.set_state('ended')

    def recipient_answered(self, relocate):
        relocate.events.publish('answered', relocate)
        if 'answer' in relocate.completions:
            completer = RelocateCompleter(self._amid, self._ari)
            if Channel(relocate.relocated_channel, self._ari).is_in_stasis():
                completer.bridge(relocate)
                self._ari.channels.hangup(channelId=relocate.initiator_channel)
                relocate.set_state('ended')
            else:
                completer.move_to_stasis(relocate)
                relocate.set_state('waiting_for_relocated')
        elif 'api' in relocate.completions:
            relocate.set_state('waiting_for_completion')
        else:
            raise NotImplementedError()

    def complete(self, relocate):
        raise RelocateCompletionError('Requested completion is too early')


@state
class RelocateStateWaitingForCompletion(RelocateState):

    name = 'waiting_for_completion'

    def complete(self, relocate):
        completer = RelocateCompleter(self._amid, self._ari)

        if Channel(relocate.relocated_channel, self._ari).is_in_stasis():
            completer.bridge(relocate)
            self._ari.channels.hangup(channelId=relocate.initiator_channel)
            relocate.set_state('ended')
        else:
            completer.move_to_stasis(relocate)
            relocate.set_state('waiting_for_relocated')

    def relocated_hangup(self, relocate):
        self._ari.channels.hangup(channelId=relocate.recipient_channel)
        relocate.set_state('ended')

    def initiator_hangup(self, relocate):
        self._ari.channels.hangup(channelId=relocate.recipient_channel)
        relocate.set_state('ended')

    def recipient_hangup(self, relocate):
        relocate.set_state('ended')


@state
class RelocateStateWaitingForRelocated(RelocateState):

    name = 'waiting_for_relocated'

    def relocated_answered(self, relocate):
        RelocateCompleter(self._amid, self._ari).bridge(relocate)

        relocate.set_state('ended')

    def relocated_hangup(self, relocate):
        self._ari.channels.hangup(channelId=relocate.recipient_channel)
        relocate.set_state('ended')

    def initiator_hangup(self, relocate):
        pass

    def recipient_hangup(self, relocate):
        self._ari.channels.hangup(channelId=relocate.relocated_channel)
        relocate.set_state('ended')

    def complete(self, relocate):
        pass


@state
class RelocateStateEnded(RelocateState):

    name = 'ended'

    def recipient_hangup(self, relocate):
        pass

    def initiator_hangup(self, relocate):
        pass

    def relocated_hangup(self, relocate):
        pass

    def complete(self, relocate):
        pass
