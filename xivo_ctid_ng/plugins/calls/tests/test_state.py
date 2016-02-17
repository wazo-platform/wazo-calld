# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import calling
from hamcrest import instance_of
from hamcrest import raises
from mock import Mock
from unittest import TestCase

from ..state import CallState
from ..state import StateFactory


class TestStateFactory(TestCase):

    def test_make_before_set_dependencies(self):
        factory = StateFactory()

        assert_that(calling(factory.make).with_args('state-name'), raises(RuntimeError))

    def test_make_unknown_state(self):
        factory = StateFactory()
        factory.set_dependencies(ari=Mock(), stat_sender=Mock())

        assert_that(calling(factory.make).with_args('state-name'), raises(KeyError))

    def test_make_valid_state(self):
        factory = StateFactory()
        factory.set_dependencies(ari=Mock(), stat_sender=Mock())

        @factory.state
        class MyState(CallState):
            name = 'my-state'

        assert_that(factory.make('my-state'), instance_of(MyState))
