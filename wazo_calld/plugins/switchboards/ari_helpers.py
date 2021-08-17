# Copyright 2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from ari.exceptions import ARINotFound

from .constants import BRIDGE_QUEUE_ID


class Switchboard:
    def __init__(self, switchboard_uuid, ari):
        self.uuid = switchboard_uuid
        self._ari = ari

    def queued_call_ids(self):
        bridge_id = BRIDGE_QUEUE_ID.format(uuid=self.uuid)
        try:
            bridge = self._ari.bridges.get(bridgeId=bridge_id)
        except ARINotFound:
            return []

        channel_ids = bridge.json['channels']
        return channel_ids
