# Copyright 2016-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests

from hamcrest import assert_that
from hamcrest import calling
from hamcrest import is_
from hamcrest import raises
from unittest.mock import Mock
from unittest import TestCase

from ..ami import extension_exists
from ..ami import moh_class_exists
from ..exceptions import WazoAmidError

SOME_EXTEN = 'some-exten'
SOME_CONTEXT = 'some-context'


class TestExtensionExists(TestCase):
    def setUp(self):
        self.amid = Mock()

    def test_given_no_amid_when_extension_exists_then_raise_exception(self):
        self.amid.action.side_effect = requests.RequestException

        assert_that(
            (calling(extension_exists).with_args(self.amid, SOME_EXTEN, SOME_CONTEXT)),
            raises(WazoAmidError),
        )

    def test_given_invalid_context_when_extension_exists_then_return_false(self):
        self.amid.action.return_value = [
            {"Message": "Did not find context unknown", "Response": "Error"}
        ]

        assert_that(extension_exists(self.amid, SOME_EXTEN, SOME_CONTEXT), is_(False))

    def test_given_invalid_extension_when_extension_exists_then_return_false(self):
        self.amid.action.return_value = [
            {
                "Message": "Did not find extension unknown@some-context",
                "Response": "Error",
            }
        ]

        assert_that(extension_exists(self.amid, SOME_EXTEN, SOME_CONTEXT), is_(False))

    def test_given_only_hint_priority_when_extension_exists_then_return_false(self):
        self.amid.action.return_value = [
            {
                "EventList": "start",
                "Message": "DialPlan list will follow",
                "Response": "Success",
            },
            {
                "Extension": "some-exten",
                "Priority": "hint",
                "Application": "PJSIP/some-sip",
                "Registrar": "pbx_config",
                "Context": "some-context",
                "Event": "ListDialplan",
            },
            {
                "ListPriorities": "1",
                "EventList": "Complete",
                "ListItems": "1",
                "ListContexts": "1",
                "ListExtensions": "1",
                "Event": "ShowDialPlanComplete",
            },
        ]

        assert_that(extension_exists(self.amid, SOME_EXTEN, SOME_CONTEXT), is_(False))

    def test_given_existing_extension_when_extension_exists_then_return_true(self):
        self.amid.action.return_value = [
            {
                "EventList": "start",
                "Message": "DialPlan list will follow",
                "Response": "Success",
            },
            {
                "Extension": "some-exten",
                "Priority": "1",
                "Application": "PJSIP/some-sip",
                "Registrar": "pbx_config",
                "Context": "some-context",
                "Event": "ListDialplan",
            },
            {
                "ListPriorities": "1",
                "EventList": "Complete",
                "ListItems": "1",
                "ListContexts": "1",
                "ListExtensions": "1",
                "Event": "ShowDialPlanComplete",
            },
        ]

        assert_that(extension_exists(self.amid, SOME_EXTEN, SOME_CONTEXT), is_(True))

    def test_given_garbage_when_moh_class_exists_then_false(self):
        amid = Mock()
        moh_class = 'default'
        amid.command.return_value = {
            'response': ['default', 'Garbage: default', 'ClassGarbage: default']
        }

        result = moh_class_exists(amid, moh_class)

        assert_that(result, is_(False))

    def test_given_unknown_moh_class_when_moh_class_exists_then_false(self):
        amid = Mock()
        moh_class = 'default'
        amid.command.return_value = {'response': ['Class: other', 'Class: another']}

        result = moh_class_exists(amid, moh_class)

        assert_that(result, is_(False))

    def test_given_moh_class_exists_when_moh_class_exists_then_true(self):
        amid = Mock()
        moh_class = 'default'
        amid.command.return_value = {'response': ['Class: default', 'Class: another']}

        result = moh_class_exists(amid, moh_class)

        assert_that(result, is_(True))
