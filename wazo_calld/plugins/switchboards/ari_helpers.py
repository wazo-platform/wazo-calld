# Copyright 2021-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from ari.exceptions import ARINotFound

from .constants import BRIDGE_QUEUE_ID


class Switchboard:
    def __init__(self, switchboard_uuid, ari):
        self.uuid = switchboard_uuid
        self._ari = ari
        self.bridge_id = BRIDGE_QUEUE_ID.format(uuid=self.uuid)

    def queued_call_ids(self):
        try:
            bridge = self._ari.bridges.get(bridgeId=self.bridge_id)
        except ARINotFound:
            return []

        channel_ids = bridge.json['channels']
        return channel_ids

    def has_queued_call(self, call_id):
        return call_id in self.queued_call_ids()

    def get_bridge(self):
        return self._ari.bridges.get(bridgeId=self.bridge_id)
