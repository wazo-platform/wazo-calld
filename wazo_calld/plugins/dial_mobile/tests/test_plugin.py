# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase
from unittest.mock import Mock, patch, sentinel

from ..plugin import Plugin


class TestPlugin(TestCase):
    def _dependencies(self):
        config = {
            'uuid': sentinel.service_uuid,
            'bus': sentinel.bus_config,
            'amid': {},
            'auth': {},
            'confd': {},
        }
        return {
            'ari': Mock(),
            'pubsub': Mock(),
            'bus_consumer': Mock(),
            'token_changed_subscribe': Mock(),
            'config': config,
            'bus_publisher': Mock(name='shared_bus_publisher'),
        }

    @patch('wazo_calld.plugins.dial_mobile.plugin.CallbackCollector')
    @patch('wazo_calld.plugins.dial_mobile.plugin.EventHandler')
    @patch('wazo_calld.plugins.dial_mobile.plugin.DialMobileStasis')
    @patch('wazo_calld.plugins.dial_mobile.plugin.DialMobileService')
    @patch('wazo_calld.plugins.dial_mobile.plugin.Notifier')
    @patch('wazo_calld.plugins.dial_mobile.plugin.CoreBusPublisher')
    @patch('wazo_calld.plugins.dial_mobile.plugin.ConfdClient')
    @patch('wazo_calld.plugins.dial_mobile.plugin.AuthClient')
    @patch('wazo_calld.plugins.dial_mobile.plugin.AmidClient')
    def test_push_notifications_use_a_dedicated_bus_publisher(
        self,
        _amid,
        _auth,
        _confd,
        core_bus_publisher,
        notifier,
        *_mocks,
    ):
        dependencies = self._dependencies()

        Plugin().load(dependencies)

        # A dedicated publisher is built from calld's bus config, in the same
        # argument order as controller.py: from_config(service_uuid, bus_config).
        # Distinct sentinels for uuid vs bus make a swapped-argument bug fail here.
        core_bus_publisher.from_config.assert_called_once_with(
            sentinel.service_uuid, sentinel.bus_config
        )
        # The Notifier must receive that dedicated publisher -- NOT the shared
        # dependencies['bus_publisher'] (which is flow-controlled under load).
        # This assertion fails if production still wires in the shared publisher.
        dedicated_publisher = core_bus_publisher.from_config.return_value
        notifier.assert_called_once_with(dedicated_publisher)
