# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import uuid

from ari.exceptions import ARIException, ARINotFound

from wazo_calld.plugin_helpers.ari_ import Channel
from wazo_calld.plugin_helpers import ami
from wazo_calld.plugin_helpers.exceptions import NotEnoughChannels, TooManyChannels

from .exceptions import (
    AdhocConferenceCreationError,
    HostCallNotFound,
    HostPermissionDenied,
    ParticipantCallNotFound,
)

import logging

logger = logging.getLogger(__name__)


class AdhocConferencesService:

    def __init__(self, amid_client, ari):
        self._amid_client = amid_client
        self._ari = ari

    def create_from_user(self, host_call_id, participant_call_ids, user_uuid):
        logger.debug('creating adhoc conference from user %s with host %s and participants %s', user_uuid, host_call_id, participant_call_ids)
        host_channel = Channel(host_call_id, self._ari)
        if not host_channel.exists():
            raise HostCallNotFound(host_call_id)

        for participant_call_id in participant_call_ids:
            if not Channel(participant_call_id, self._ari).exists():
                raise ParticipantCallNotFound(host_call_id)

        if host_channel.user() != user_uuid:
            raise HostPermissionDenied(host_call_id, host_channel.user())

        adhoc_conference_id = str(uuid.uuid4())
        logger.debug('creating adhoc conference %s', adhoc_conference_id)

        logger.debug('adhoc conference %s: looking for peer of host %s', adhoc_conference_id, host_call_id)
        host_peer_channel_id = self._find_call_peer(host_call_id)

        self._redirect_host(host_call_id, host_peer_channel_id, adhoc_conference_id)

        remaining_participant_call_ids = set(participant_call_ids) - {host_peer_channel_id}
        logger.debug('adhoc conference %s: remaining participants %s', adhoc_conference_id, remaining_participant_call_ids)
        for participant_call_id in remaining_participant_call_ids:
            logger.debug('adhoc conference %s: looking for peer of participant %s', adhoc_conference_id, participant_call_id)
            discarded_host_channel_id = self._find_call_peer(participant_call_id)

            logger.debug('adhoc conference %s: processing participant %s and peer %s', adhoc_conference_id, participant_call_id, discarded_host_channel_id)
            self._redirect_participant(participant_call_id, discarded_host_channel_id, adhoc_conference_id)

        return {
            'conference_id': adhoc_conference_id,
        }

    def _find_call_peer(self, call_id):
        try:
            return Channel(call_id, self._ari).only_connected_channel().id
        except (TooManyChannels, NotEnoughChannels):
            raise  # replace me

    def _redirect_host(self, host_call_id, host_peer_channel_id, adhoc_conference_id):
        try:
            host_channel = self._ari.channels.get(channelId=host_call_id)
        except ARINotFound:
            raise AdhocConferenceCreationError('host call was hungup')
        try:
            host_peer_channel = self._ari.channels.get(channelId=host_peer_channel_id)
        except ARINotFound:
            raise AdhocConferenceCreationError('participant call was hungup')

        logger.debug('adhoc conference %s: redirecting host call %s and peer %s', adhoc_conference_id, host_call_id, host_peer_channel_id)
        try:
            host_channel.setChannelVar(variable='WAZO_ADHOC_CONFERENCE_ID',
                                       value=adhoc_conference_id,
                                       bypassStasis=True)
            host_peer_channel.setChannelVar(variable='WAZO_ADHOC_CONFERENCE_ID',
                                            value=adhoc_conference_id,
                                            bypassStasis=True)
        except ARIException as e:
            logger.exception('ARI error: %s', e)
            return
        ami.redirect(
            self._amid_client,
            host_peer_channel.json['name'],
            context='convert_to_stasis',
            exten='adhoc_conference',
            extra_channel=host_channel.json['name'],
        )

    def _redirect_participant(self, participant_channel_id, discarded_host_channel_id, adhoc_conference_id):
        try:
            discarded_host_channel = self._ari.channels.get(channelId=discarded_host_channel_id)
        except ARINotFound:
            raise AdhocConferenceCreationError('host call was hungup')
        try:
            participant_channel = self._ari.channels.get(channelId=participant_channel_id)
        except ARINotFound:
            raise AdhocConferenceCreationError('participant call was hungup')

        logger.debug('adhoc conference %s: redirecting participant call %s and discarding peer %s', adhoc_conference_id, participant_channel_id, discarded_host_channel_id)
        try:
            participant_channel.setChannelVar(variable='WAZO_ADHOC_CONFERENCE_ID',
                                              value=adhoc_conference_id,
                                              bypassStasis=True)
        except ARIException as e:
            logger.exception('ARI error: %s', e)
            return
        ami.redirect(
            self._amid_client,
            participant_channel.json['name'],
            context='convert_to_stasis',
            exten='adhoc_conference',
            extra_channel=discarded_host_channel.json['name'],
            extra_context='convert_to_stasis',
            extra_exten='h'
        )
