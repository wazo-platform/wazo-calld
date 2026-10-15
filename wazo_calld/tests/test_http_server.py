# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import patch

import pytest

from wazo_calld.http_server import HTTPServer, api, app


@pytest.fixture
def http_server():
    config = {
        'auth': {},
        'rest_api': {
            'listen': '127.0.0.1',
            'port': 9500,
            'min_threads': 1,
            'max_threads': 1,
            'certificate': None,
            'private_key': None,
            'cors': {'enabled': False},
        },
        'metrics': {'enabled': False},
    }
    return HTTPServer(config)


def test_stop_before_run_does_not_raise_and_sets_the_tombstone(http_server):
    http_server.stop()

    assert http_server._stopped.is_set()


@patch('wazo_calld.http_server.wsgi')
def test_run_after_stop_does_not_start_the_server(wsgi, http_server):
    http_server.stop()
    http_server.run()

    wsgi.DynamicWSGIServer.return_value.start.assert_not_called()


@patch('wazo_calld.http_server.wsgi')
def test_stop_after_run_stops_the_server(wsgi, http_server):
    http_server.run()
    http_server.stop()

    wsgi.DynamicWSGIServer.return_value.stop.assert_called_once_with()


@patch('wazo_calld.http_server.init_flask_metrics')
def test_metrics_enabled_instruments_the_app(init_flask_metrics):
    config = {
        'auth': {},
        'rest_api': {'cors': {'enabled': False}},
        'metrics': {'enabled': True},
    }

    HTTPServer(config)

    init_flask_metrics.assert_called_once_with(app, api)


@patch('wazo_calld.http_server.init_flask_metrics')
def test_metrics_disabled_does_not_instrument_the_app(init_flask_metrics):
    config = {
        'auth': {},
        'rest_api': {'cors': {'enabled': False}},
        'metrics': {'enabled': False},
    }

    HTTPServer(config)

    init_flask_metrics.assert_not_called()
