# Copyright 2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock, sentinel as s

from wazo_calld.plugins.switchboards.services import SwitchboardsService


class TestSwitchboardService(TestCase):
    def setUp(self):
        self.ari = Mock()
        self.asyncio = Mock()
        self.confd = Mock()
        self.notifier = Mock()

        self.service = SwitchboardsService(self.ari, self.asyncio, self.confd, self.notifier)

    def test_moh_on_new_queued_call_when_defined(self):
        self.confd.switchboards.get.return_value = {'queue_music_on_hold': s.moh_class}
        bridge = self.ari.bridges.get.return_value
        self.ari.channels.getChannelVar.return_value = {'value': 'mock'}
        bridge.json = {'channels': []}

        self.service.new_queued_call(self, s.tenant_uuid, s.switchboard_uuid)

        bridge.startMoh.assert_called_once_with(mohClass=s.moh_class)

    def test_moh_on_new_queued_call_when_not_defined(self):
        self.confd.switchboards.get.return_value = {'queue_music_on_hold': None}
        bridge = self.ari.bridges.get.return_value
        self.ari.channels.getChannelVar.return_value = {'value': 'mock'}
        bridge.json = {'channels': []}

        self.service.new_queued_call(self, s.tenant_uuid, s.switchboard_uuid)

        bridge.startMoh.assert_called_once_with()

    def test_moh_on_hold_call_when_defined(self):
        self.confd.switchboards.get.return_value = {
            'waiting_room_music_on_hold': s.moh_class
        }
        bridge = self.ari.bridges.get.return_value
        self.ari.bridges.list.return_value = [bridge]
        bridge.json = {'channels': []}

        self.service.hold_call(self, s.tenant_uuid, s.switchboard_uuid)

        bridge.startMoh.assert_called_once_with(mohClass=s.moh_class)

    def test_moh_on_hold_call_when_not_defined(self):
        self.confd.switchboards.get.return_value = {'waiting_room_music_on_hold': None}
        bridge = self.ari.bridges.get.return_value
        self.ari.bridges.list.return_value = [bridge]
        bridge.json = {'channels': []}

        self.service.hold_call(self, s.tenant_uuid, s.switchboard_uuid)

        bridge.startMoh.assert_called_once_with()
