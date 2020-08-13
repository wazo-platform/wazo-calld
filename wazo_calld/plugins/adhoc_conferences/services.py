# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_calld.plugin_helpers.ari_ import Channel

from .exceptions import (
    HostCallNotFound,
    HostPermissionDenied,
    ParticipantCallNotFound,
)


class AdhocConferencesService:

    def __init__(self, ari):
        self._ari = ari

    def create_from_user(self, host_call_id, participant_call_ids, user_uuid):
        host_channel = Channel(host_call_id, self._ari)
        if not host_channel.exists():
            raise HostCallNotFound(host_call_id)

        for participant_call_id in participant_call_ids:
            if not Channel(participant_call_id, self._ari).exists():
                raise ParticipantCallNotFound(host_call_id)

        if host_channel.user() != user_uuid:
            raise HostPermissionDenied(host_call_id, host_channel.user())
