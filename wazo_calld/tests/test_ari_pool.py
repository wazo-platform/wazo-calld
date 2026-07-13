# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Behavioral test for the ARI client connection pool size.

wazo-calld routes every ARI REST call through one process-wide
``requests.Session``. When more calls are in flight than the session's
``pool_maxsize``, urllib3 logs ``Connection pool is full, discarding
connection`` and drops the surplus connection. This test reproduces that
condition against a local stub server (a short ``sleep`` holds each connection
open so concurrency exceeds the pool) and asserts that a pool sized to the load
no longer discards connections.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from unittest import TestCase

from hamcrest import assert_that, empty, is_not

from ..ari_ import _build_ari_http_client


class _SlowHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Hold the connection long enough that all concurrent requests are
        # in flight at once (this is what netem injected in the load test).
        time.sleep(0.2)
        body = b'{}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # silence the default stderr access log during tests


class _PoolFullCollector(logging.Handler):
    def __init__(self):
        super().__init__()
        self.warnings = []

    def emit(self, record):
        if 'Connection pool is full' in record.getMessage():
            self.warnings.append(record.getMessage())


class TestAriConnectionPool(TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), _SlowHandler)
        self.url = f'http://127.0.0.1:{self.server.server_address[1]}/'
        self.server_thread = Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

        self.collector = _PoolFullCollector()
        self.logger = logging.getLogger('urllib3.connectionpool')
        self._previous_level = self.logger.level
        self.logger.setLevel(logging.WARNING)
        self.logger.addHandler(self.collector)

    def tearDown(self):
        self.logger.removeHandler(self.collector)
        self.logger.setLevel(self._previous_level)
        self.server.shutdown()
        self.server.server_close()

    def _hammer(self, pool_size, concurrency):
        http_client = _build_ari_http_client(self.url, 'xivo', 'secret', pool_size)
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [
                pool.submit(http_client.session.get, self.url)
                for _ in range(concurrency)
            ]
            for future in futures:
                future.result().close()

    def test_pool_smaller_than_concurrency_discards_connections(self):
        self._hammer(pool_size=2, concurrency=10)

        assert_that(self.collector.warnings, is_not(empty()))

    def test_pool_large_enough_keeps_all_connections(self):
        self._hammer(pool_size=20, concurrency=10)

        assert_that(self.collector.warnings, empty())
