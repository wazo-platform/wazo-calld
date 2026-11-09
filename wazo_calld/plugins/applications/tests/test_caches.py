# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from functools import partial
from unittest import TestCase
from unittest.mock import Mock, patch

import requests
from hamcrest import assert_that, calling, equal_to, raises

from wazo_calld.plugin_helpers.retry_thread import RetryThread

from ..caches import confd_is_ready


class TestConfdIsReady(TestCase):
    def setUp(self):
        self.confd_client = Mock()

    def test_a_connection_error_is_not_ready(self):
        self.confd_client.infos.get.side_effect = requests.ConnectionError

        assert_that(confd_is_ready(self.confd_client), equal_to(False))

    def test_an_http_error_is_ready(self):
        self.confd_client.infos.get.side_effect = requests.HTTPError

        assert_that(confd_is_ready(self.confd_client), equal_to(True))

    def test_an_answer_is_ready(self):
        self.confd_client.infos.get.return_value = {'uuid': 'abc'}

        assert_that(confd_is_ready(self.confd_client), equal_to(True))

    def test_a_read_timeout_propagates(self):
        self.confd_client.infos.get.side_effect = requests.ReadTimeout

        assert_that(
            calling(confd_is_ready).with_args(self.confd_client),
            raises(requests.ReadTimeout),
        )

    def test_a_read_timeout_is_not_a_connection_error(self):
        assert_that(
            issubclass(requests.ReadTimeout, requests.ConnectionError), equal_to(False)
        )


class TestConfdIsReadyRetried(TestCase):
    def test_a_read_timeout_is_retried_until_confd_answers(self):
        confd_client = Mock()
        confd_client.infos.get.side_effect = [requests.ReadTimeout, {'uuid': 'abc'}]
        stop_event = Mock()
        stop_event.is_set.return_value = False
        stop_event.wait.return_value = False
        ready = Mock()
        with patch(
            'wazo_calld.plugin_helpers.retry_thread.Event', return_value=stop_event
        ):
            thread = RetryThread(
                'wazo-confd', partial(confd_is_ready, confd_client), delays=[1]
            )
        thread.subscribe(ready)

        thread.start()
        assert thread._thread is not None
        thread._thread.join(timeout=5)
        if thread._thread.is_alive():
            thread.stop()
            raise AssertionError('the wazo-confd retry thread did not end')

        assert_that(confd_client.infos.get.call_count, equal_to(2))
        ready.assert_called_once_with()
