# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from collections.abc import Callable
from unittest import TestCase
from unittest.mock import MagicMock, Mock, patch

from hamcrest import assert_that, equal_to

from ..caches import confd_is_ready
from ..plugin import Plugin

PLUGIN = 'wazo_calld.plugins.applications.plugin'


class TestPluginWaitsForConfd(TestCase):
    @patch(f'{PLUGIN}.RetryThread')
    @patch(f'{PLUGIN}.ConfdClient')
    @patch(f'{PLUGIN}.AuthClient', Mock())
    @patch(f'{PLUGIN}.AmidClient', Mock())
    def test_confd_is_polled_every_second_from_load_until_stopping(
        self, ConfdClient, RetryThread
    ):
        subscriptions: dict[str, Callable[[object], None]] = {}
        pubsub = Mock()
        pubsub.subscribe.side_effect = subscriptions.__setitem__
        dependencies = MagicMock()
        dependencies.__getitem__.side_effect = lambda key: (
            pubsub if key == 'pubsub' else MagicMock(name=key)
        )

        Plugin().load(dependencies)

        (name, task), kwargs = RetryThread.call_args
        assert_that(name, equal_to('wazo-confd'))
        assert_that(kwargs, equal_to({'delays': [1]}))
        assert_that(task.func, equal_to(confd_is_ready))
        assert_that(task.args, equal_to((ConfdClient.return_value,)))
        thread = RetryThread.return_value
        thread.subscribe.assert_called_once()
        thread.start.assert_called_once_with()
        thread.stop.assert_not_called()

        subscriptions['stopping'](None)

        thread.stop.assert_called_once_with()
