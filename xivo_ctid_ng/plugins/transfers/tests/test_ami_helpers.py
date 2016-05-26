# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import requests

from hamcrest import assert_that
from hamcrest import calling
from hamcrest import is_
from hamcrest import raises
from mock import Mock
from unittest import TestCase

from ..ami_helpers import extension_exists
from ..exceptions import XiVOAmidError

SOME_EXTEN = 'some-exten'
SOME_CONTEXT = 'some-context'


class TestExtensionExists(TestCase):

    def setUp(self):
        self.amid = Mock()

    def test_given_no_amid_when_extension_exists_then_raise_exception(self):
        self.amid.action.side_effect = requests.RequestException

        assert_that((calling(extension_exists)
                     .with_args(self.amid, SOME_EXTEN, SOME_CONTEXT)),
                    raises(XiVOAmidError))

    def test_given_invalid_context_when_extension_exists_then_return_false(self):
        self.amid.action.return_value = [
            {
                "Message": "Did not find context unknown",
                "Response": "Error"
            }
        ]

        assert_that(extension_exists(self.amid, SOME_EXTEN, SOME_CONTEXT), is_(False))

    def test_given_invalid_extension_when_extension_exists_then_return_false(self):
        self.amid.action.return_value = [
            {
                "Message": "Did not find extension unknown@some-context",
                "Response": "Error"
            }
        ]

        assert_that(extension_exists(self.amid, SOME_EXTEN, SOME_CONTEXT), is_(False))

    def test_given_only_hint_priority_when_extension_exists_then_return_false(self):
        self.amid.action.return_value = [
            {
                "EventList": "start",
                "Message": "DialPlan list will follow",
                "Response": "Success"
            },
            {
                "Extension": "some-exten",
                "Priority": "hint",
                "Application": "SIP/some-sip",
                "Registrar": "pbx_config",
                "Context": "some-context",
                "Event": "ListDialplan"
            },
            {
                "ListPriorities": "1",
                "EventList": "Complete",
                "ListItems": "1",
                "ListContexts": "1",
                "ListExtensions": "1",
                "Event": "ShowDialPlanComplete"
            }
        ]

        assert_that(extension_exists(self.amid, SOME_EXTEN, SOME_CONTEXT), is_(False))

    def test_given_existing_extension_when_extension_exists_then_return_true(self):
        self.amid.action.return_value = [
            {
                "EventList": "start",
                "Message": "DialPlan list will follow",
                "Response": "Success"
            },
            {
                "Extension": "some-exten",
                "Priority": "1",
                "Application": "SIP/some-sip",
                "Registrar": "pbx_config",
                "Context": "some-context",
                "Event": "ListDialplan"
            },
            {
                "ListPriorities": "1",
                "EventList": "Complete",
                "ListItems": "1",
                "ListContexts": "1",
                "ListExtensions": "1",
                "Event": "ShowDialPlanComplete"
            }
        ]

        assert_that(extension_exists(self.amid, SOME_EXTEN, SOME_CONTEXT), is_(True))
