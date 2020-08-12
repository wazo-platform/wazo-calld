# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from ari.exceptions import ARINotFound
from .exceptions import HostCallNotFound, ParticipantCallNotFound


class AdhocConferencesService:

    def __init__(self, ari):
        self._ari = ari

    def create_from_user(self, host_call_id, participant_call_ids, user_uuid):
        try:
            host_channel = self._ari.channels.get(channelId=host_call_id)
        except ARINotFound:
            raise HostCallNotFound(host_call_id)

        for participant_call_id in participant_call_ids:
            try:
                participant_channel = self._ari.channels.get(channelId=participant_call_id)
            except ARINotFound:
                raise ParticipantCallNotFound(host_call_id)
