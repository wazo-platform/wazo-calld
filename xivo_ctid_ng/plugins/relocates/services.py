# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from ari.exceptions import ARINotFound
from xivo_ctid_ng.exceptions import UserPermissionDenied
from xivo_ctid_ng.helpers.ari_ import Channel
from xivo_ctid_ng.helpers.confd import User
from xivo_ctid_ng.helpers.exceptions import (
    NotEnoughChannels,
    TooManyChannels,
    InvalidUserLine,
    InvalidUserUUID,
)

from .exceptions import TooManyChannelCandidates
from .exceptions import RelocateAlreadyStarted
from .exceptions import RelocateCreationError
from .relocate import Relocate

logger = logging.getLogger(__name__)


class DestinationFactory(object):

    def __init__(self, ari, confd_client):
        self.ari = ari
        self.confd_client = confd_client

    def from_type(self, type_, details):
        if type_ == 'interface':
            return InterfaceDestination(details)
        raise NotImplementedError(type_)


class InvalidDestination(Exception):
    def __init__(self, details):
        self._details = details
        super(InvalidDestination, self).__init__(details)


class Destination(object):
    def __init__(self, details):
        self._details = details
        self.assert_is_valid()

    def assert_is_valid(self):
        if not self.is_valid():
            raise InvalidDestination(self._details)


class InterfaceDestination(Destination):
    def __init__(self, details):
        self._interface = details['interface']
        super(InterfaceDestination, self).__init__(details)

    def is_valid(self):
        return True

    def ari_endpoint(self):
        return self._interface


class RelocatesService(object):

    def __init__(self, ari, confd_client, relocates, state_factory, relocate_lock):
        self.ari = ari
        self.confd_client = confd_client
        self.state_factory = state_factory
        self.destination_factory = DestinationFactory(ari, confd_client)
        self.relocates = relocates
        self.relocate_lock = relocate_lock

    def create(self, initiator_call, destination, location):
        try:
            relocated_channel = Channel(initiator_call, self.ari).only_connected_channel()
        except TooManyChannels as e:
            raise TooManyChannelCandidates(e.channels)
        except NotEnoughChannels as e:
            raise RelocateCreationError('relocated channel not found')

        try:
            initiator_channel = self.ari.channels.get(channelId=initiator_call)
        except ARINotFound:
            raise RelocateCreationError('channel not found')

        destination = self.destination_factory.from_type(destination, location)

        if (not self.relocate_lock.acquire(initiator_call)
                or self.relocates.find_by_channel(initiator_call)):
            raise RelocateAlreadyStarted(initiator_call)

        relocate = Relocate(self.state_factory, relocated_channel.id, initiator_channel.id)
        self.relocates.add(relocate)
        try:
            with relocate.locked():
                relocate.initiate(destination)
        finally:
            self.relocate_lock.release(initiator_call)

        return relocate

    def create_from_user(self, initiator_call, destination, location, user_uuid):
        if not Channel(initiator_call, self.ari).exists():
            raise RelocateCreationError('initiator channel not found')

        if Channel(initiator_call, self.ari).user() != user_uuid:
            raise UserPermissionDenied(user_uuid, {'call': initiator_call})

        if destination == 'line':
            try:
                destination_interface = User(user_uuid, self.confd_client).line(location['line_id']).interface()
            except (InvalidUserUUID, InvalidUserLine):
                raise RelocateCreationError('invalid line for user', details={'user_uuid': user_uuid, 'line_id': location['line_id']})
        destination = 'interface'
        location = {'interface': destination_interface}

        return self.create(initiator_call, destination, location)
