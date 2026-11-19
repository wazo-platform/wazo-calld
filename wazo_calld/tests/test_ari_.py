# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import threading
import time
from unittest import TestCase
from unittest.mock import Mock, patch

from hamcrest import assert_that, equal_to, less_than

from ..ari_ import ARIClientProxy, CoreARI, _build_ari_http_client


class TestBuildAriHttpClient(TestCase):
    def test_adapter_uses_configured_pool_size(self):
        http_client = _build_ari_http_client(
            'http://localhost:5039', 'xivo', 'secret', pool_size=25
        )

        adapter = http_client.session.get_adapter('http://localhost:5039')
        assert_that(adapter._pool_maxsize, equal_to(25))


class TestARIClientProxyPoolSize(TestCase):
    def test_explicit_pool_size(self):
        proxy = ARIClientProxy('http://localhost:5039', 'xivo', 'secret', pool_size=42)

        assert_that(proxy._pool_size, equal_to(42))


def core_ari_config(startup_connection_delay):
    return {
        'connection': {
            'base_url': 'http://localhost:5039',
            'username': 'xivo',
            'password': 'secret',
            'pool_size': 5,
        },
        'startup_connection_delay': startup_connection_delay,
    }


def join_initialization(core_ari):
    thread = core_ari._initialization_thread._thread
    thread.join(timeout=5)
    assert not thread.is_alive(), 'the ARI initialization did not end'


class TestCoreARIInitialization(TestCase):
    def test_init_client_starts_a_retry_thread_named_ari_with_the_startup_delay(self):
        with patch('wazo_calld.ari_.RetryThread') as RetryThread:
            core_ari = CoreARI(core_ari_config(7), Mock())
            RetryThread.return_value.start.assert_not_called()

            core_ari.init_client()

        RetryThread.assert_called_once_with('ARI', core_ari.client.init, delays=[7])
        RetryThread.return_value.start.assert_called_once_with()

    def test_success_publishes_client_initialized_to_every_subscriber(self):
        with patch.object(ARIClientProxy, 'init', side_effect=[Exception, True]):
            core_ari = CoreARI(core_ari_config(0), Mock())
            first, second = Mock(), Mock()
            core_ari.client_initialized_subscribe(first)
            core_ari.client_initialized_subscribe(second)

            core_ari.init_client()
            join_initialization(core_ari)

        first.assert_called_once_with(None)
        second.assert_called_once_with(None)

    def test_stop_before_init_client_raises_nothing(self):
        core_ari = CoreARI(core_ari_config(1), Mock())

        core_ari.stop()

    def test_stop_interrupts_the_startup_delay(self):
        called = threading.Event()

        def unreachable():
            called.set()
            raise ConnectionError('ARI unreachable')

        with patch.object(ARIClientProxy, 'init', side_effect=unreachable):
            core_ari = CoreARI(core_ari_config(60), Mock())
            core_ari.init_client()
            retry_thread = core_ari._initialization_thread
            self.addCleanup(retry_thread._stop_event.set)
            assert called.wait(timeout=5)

            started = time.monotonic()
            core_ari.stop()

        assert_that(time.monotonic() - started, less_than(1))
        thread = retry_thread._thread
        assert thread is not None
        assert_that(thread.is_alive(), equal_to(False))
