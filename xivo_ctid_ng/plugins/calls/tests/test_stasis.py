# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that, equal_to, is_
from unittest import TestCase

from ..stasis import connect_event_originator
from ..stasis import get_stasis_start_app
from ..stasis import is_connect_event


class TestCallsStasis(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_get_stasis_start_app_invalid(self):
        assert_that(get_stasis_start_app({}), equal_to((None, None)))
        assert_that(get_stasis_start_app({'args': []}), equal_to((None, None)))

    def test_get_stasis_start_app_valid(self):
        event = {
            'application': 'myapp',
            'args': ['red']
        }

        result = get_stasis_start_app(event)

        assert_that(result, equal_to(('myapp', 'red')))

    def test_is_connect_event_false(self):
        assert_that(is_connect_event({}), equal_to(False))
        assert_that(is_connect_event({'args': []}), equal_to(False))

    def test_is_connect_event_true(self):
        event = {
            'application': 'myapp',
            'args': ['red', 'dialed_from']
        }

        result = is_connect_event(event)

        assert_that(result, is_(True))

    def test_connect_event_originator_invalid(self):
        assert_that(connect_event_originator({}), equal_to(None))
        assert_that(connect_event_originator({'args': []}), equal_to(None))

    def test_connect_event_originator_valid(self):
        event = {
            'application': 'myapp',
            'args': ['red', 'dialed_from', 'channel-id']
        }

        result = connect_event_originator(event)

        assert_that(result, equal_to('channel-id'))
