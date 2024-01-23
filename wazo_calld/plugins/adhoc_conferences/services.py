# Copyright 2020-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
import uuid

from ari.exceptions import ARIException, ARINotFound, ARINotInStasis

from wazo_calld.plugin_helpers import ami
from wazo_calld.plugin_helpers.ari_ import Bridge, Channel
from wazo_calld.plugin_helpers.exceptions import (
    BridgeNotFound,
    NotEnoughChannels,
    TooManyChannels,
)

from .exceptions import (
    AdhocConferenceCreationError,
    AdhocConferenceNotFound,
    HostCallAlreadyInConference,
    HostCallNotFound,
    ParticipantCallAlreadyInConference,
    ParticipantCallNotFound,
)
from .stasis import ADHOC_CONFERENCE_STASIS_APP

logger = logging.getLogger(__name__)


class AdhocConferencesService:
    def __init__(self, amid_client, ari, notifier):
        self._amid_client = amid_client
        self._ari = ari
        self._notifier = notifier

    def create_from_user(self, host_call_id, participant_call_ids, user_uuid):
        logger.debug(
            'creating adhoc conference from user %s with host %s and participants %s',
            user_uuid,
            host_call_id,
            participant_call_ids,
        )
        host_channel = Channel(host_call_id, self._ari)
        if not host_channel.exists():
            raise HostCallNotFound(host_call_id)

        if host_channel.user() != user_uuid:
            raise HostCallNotFound(host_call_id)

        logger.debug('adhoc conference: looking for peer of host %s', host_call_id)
        try:
            host_peer_wazo_channel = self._find_peer_channel(host_call_id)
        except NotEnoughChannels:
            raise AdhocConferenceCreationError(
                f'could not determine peer of call {host_call_id}: call has no peers'
            )
        except TooManyChannels:
            raise HostCallAlreadyInConference(host_call_id)

        for participant_call_id in participant_call_ids:
            if not Channel(participant_call_id, self._ari).exists():
                raise ParticipantCallNotFound(participant_call_id)

            try:
                peer_wazo_channel = self._find_peer_channel(participant_call_id)
            except NotEnoughChannels:
                logger.error(
                    'adhoc conference: participant %s is a lone channel',
                    participant_call_id,
                )
                raise ParticipantCallNotFound(participant_call_id)
            except TooManyChannels as e:
                logger.error(
                    'adhoc conference: participant %s is already talking to %s channels',
                    participant_call_id,
                    len(list(e.channels)),
                )
                raise ParticipantCallNotFound(participant_call_id)

            if peer_wazo_channel.user() != user_uuid:
                raise ParticipantCallNotFound(participant_call_id)

        adhoc_conference_id = str(uuid.uuid4())
        tenant_uuid = host_channel.tenant_uuid()
        logger.debug('creating adhoc conference %s', adhoc_conference_id)
        self._notifier.created(adhoc_conference_id, tenant_uuid, user_uuid)

        self._redirect_host(
            host_call_id, host_peer_wazo_channel.id, adhoc_conference_id
        )

        remaining_participant_call_ids = set(participant_call_ids) - {
            host_peer_wazo_channel.id
        }
        logger.debug(
            'adhoc conference %s: remaining participants %s',
            adhoc_conference_id,
            remaining_participant_call_ids,
        )
        for participant_call_id in remaining_participant_call_ids:
            logger.debug(
                'adhoc conference %s: looking for peer of participant %s',
                adhoc_conference_id,
                participant_call_id,
            )
            discarded_host_channel_id = self._find_peer_channel(participant_call_id).id

            logger.debug(
                'adhoc conference %s: processing participant %s and peer %s',
                adhoc_conference_id,
                participant_call_id,
                discarded_host_channel_id,
            )
            self._redirect_participant(
                participant_call_id, discarded_host_channel_id, adhoc_conference_id
            )

        return {
            'conference_id': adhoc_conference_id,
        }

    def _find_peer_channel(self, call_id):
        return Channel(call_id, self._ari).only_connected_channel()

    def _redirect_host(self, host_call_id, host_peer_channel_id, adhoc_conference_id):
        try:
            host_channel = self._ari.channels.get(channelId=host_call_id)
        except ARINotFound:
            raise AdhocConferenceCreationError('host call was hungup')
        try:
            host_peer_channel = self._ari.channels.get(channelId=host_peer_channel_id)
        except ARINotFound:
            raise AdhocConferenceCreationError('participant call was hungup')

        logger.debug(
            'adhoc conference %s: redirecting host call %s and peer %s',
            adhoc_conference_id,
            host_call_id,
            host_peer_channel_id,
        )
        try:
            host_channel.setChannelVar(
                variable='WAZO_IS_ADHOC_CONFERENCE_HOST',
                value='true',
                bypassStasis=True,
            )
            host_peer_channel.setChannelVar(
                variable='WAZO_IS_ADHOC_CONFERENCE_HOST',
                value='false',
                bypassStasis=True,
            )
        except ARIException as e:
            logger.exception('ARI error: %s', e)
            return

        channel_ids = [host_channel.id, host_peer_channel.id]
        if self._channels_are_in_stasis(*channel_ids):
            try:
                self._ari_redirect(
                    host_channel.id,
                    stasis_app=ADHOC_CONFERENCE_STASIS_APP,
                    stasis_app_args=[adhoc_conference_id],
                )
                self._ari_redirect(
                    host_peer_channel.id,
                    stasis_app=ADHOC_CONFERENCE_STASIS_APP,
                    stasis_app_args=[adhoc_conference_id],
                )
            except ARIException as e:
                logger.exception('ARI error: %s', e)
                return
        else:
            try:
                host_channel.setChannelVar(
                    variable='WAZO_ADHOC_CONFERENCE_ID',
                    value=adhoc_conference_id,
                    bypassStasis=True,
                )
                host_peer_channel.setChannelVar(
                    variable='WAZO_ADHOC_CONFERENCE_ID',
                    value=adhoc_conference_id,
                    bypassStasis=True,
                )
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

    def _redirect_participant(
        self, participant_channel_id, discarded_host_channel_id, adhoc_conference_id
    ):
        try:
            discarded_host_channel = self._ari.channels.get(
                channelId=discarded_host_channel_id
            )
        except ARINotFound:
            raise AdhocConferenceCreationError('host call was hungup')
        try:
            participant_channel = self._ari.channels.get(
                channelId=participant_channel_id
            )
        except ARINotFound:
            raise AdhocConferenceCreationError('participant call was hungup')

        logger.debug(
            'adhoc conference %s: redirecting participant call %s and discarding peer %s',
            adhoc_conference_id,
            participant_channel_id,
            discarded_host_channel_id,
        )
        try:
            participant_channel.setChannelVar(
                variable='WAZO_IS_ADHOC_CONFERENCE_HOST',
                value='false',
                bypassStasis=True,
            )
        except ARIException as e:
            logger.exception('ARI error: %s', e)
            return

        try:
            participant_channel.setChannelVar(
                variable='WAZO_ADHOC_CONFERENCE_ID',
                value=adhoc_conference_id,
                bypassStasis=True,
            )
        except ARIException as e:
            logger.exception('ARI error: %s', e)
            return

        channel_ids = [participant_channel.id, discarded_host_channel.id]
        if self._channels_are_in_stasis(*channel_ids):
            try:
                self._ari_redirect(
                    participant_channel.id,
                    stasis_app=ADHOC_CONFERENCE_STASIS_APP,
                    stasis_app_args=[adhoc_conference_id],
                )
                self._ari.channels.hangup(channelId=discarded_host_channel.id)
            except ARIException as e:
                logger.exception('ARI error: %s', e)
                return
        else:
            try:
                participant_channel.setChannelVar(
                    variable='WAZO_ADHOC_CONFERENCE_ID',
                    value=adhoc_conference_id,
                    bypassStasis=True,
                )
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
                extra_exten='h',
            )

    def _channels_are_in_stasis(self, *channel_ids):
        for channel_id in channel_ids:
            if not Channel(channel_id, self._ari).is_in_stasis():
                return False
        return True

    def _ari_redirect(self, channel_id, stasis_app, stasis_app_args):
        # NOTE: Destroy bridge before moving channels
        #       to avoid to trigger cleanup from callcontrol
        try:
            bridge = Channel(channel_id, self._ari).bridge()
            if len(bridge.channel_ids()) <= 2:
                self._ari.bridges.destroy(bridgeId=bridge.id)
        except (ARINotFound, BridgeNotFound):
            pass

        try:
            self._ari.channels.move(
                channelId=channel_id,
                app=stasis_app,
                appArgs=stasis_app_args,
            )
        except ARINotInStasis:
            logger.warning(f'Channel {channel_id} not in stasis')
            raise

    def delete_from_user(self, adhoc_conference_id, user_uuid):
        bridge_helper = Bridge(adhoc_conference_id, self._ari)
        if not bridge_helper.exists():
            raise AdhocConferenceNotFound(adhoc_conference_id)

        if (
            bridge_helper.global_variables.get(variable='WAZO_HOST_USER_UUID')
            != user_uuid
        ):
            raise AdhocConferenceNotFound(adhoc_conference_id)

        bridge_helper.hangup_all()

    def add_participant_from_user(
        self, adhoc_conference_id, participant_call_id, user_uuid
    ):
        bridge_helper = Bridge(adhoc_conference_id, self._ari)
        if not bridge_helper.exists():
            raise AdhocConferenceNotFound(adhoc_conference_id)

        if not Channel(participant_call_id, self._ari).exists():
            raise ParticipantCallNotFound(participant_call_id)

        if (
            bridge_helper.global_variables.get(variable='WAZO_HOST_USER_UUID')
            != user_uuid
        ):
            raise AdhocConferenceNotFound(adhoc_conference_id)

        current_participant_call_ids = self._ari.bridges.get(
            bridgeId=adhoc_conference_id
        ).json['channels']
        if participant_call_id in current_participant_call_ids:
            raise ParticipantCallAlreadyInConference(participant_call_id)

        try:
            discarded_host_wazo_channel = self._find_peer_channel(participant_call_id)
        except NotEnoughChannels:
            logger.error(
                'adhoc conference %s: participant %s is a lone channel',
                adhoc_conference_id,
                participant_call_id,
            )
            raise ParticipantCallNotFound(participant_call_id)
        except TooManyChannels as e:
            logger.error(
                'adhoc conference %s: participant %s is already talking to %s channels',
                adhoc_conference_id,
                participant_call_id,
                len(list(e.channels)),
            )
            raise ParticipantCallNotFound(participant_call_id)

        if discarded_host_wazo_channel.user() != user_uuid:
            raise ParticipantCallNotFound(participant_call_id)

        self._redirect_participant(
            participant_call_id, discarded_host_wazo_channel.id, adhoc_conference_id
        )

    def remove_participant_from_user(
        self, adhoc_conference_id, participant_call_id, user_uuid
    ):
        bridge_helper = Bridge(adhoc_conference_id, self._ari)
        if not bridge_helper.exists():
            raise AdhocConferenceNotFound(adhoc_conference_id)

        if (
            bridge_helper.global_variables.get(variable='WAZO_HOST_USER_UUID')
            != user_uuid
        ):
            raise AdhocConferenceNotFound(adhoc_conference_id)

        if not Channel(participant_call_id, self._ari).exists():
            raise ParticipantCallNotFound(participant_call_id)

        participants = self._ari.bridges.get(bridgeId=adhoc_conference_id).json[
            'channels'
        ]
        if participant_call_id not in participants:
            raise ParticipantCallNotFound(participant_call_id)

        try:
            self._ari.channels.hangup(channelId=participant_call_id)
        except ARINotFound:
            pass
