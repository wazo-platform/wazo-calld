# Copyright 2016-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from hamcrest import assert_that
from hamcrest import is_
from unittest.mock import Mock
from unittest.mock import patch
from unittest.mock import sentinel
from unittest import TestCase

from wazo_calld.plugin_helpers.exceptions import WazoAmidError

from ..ari_helpers import hold_transferred_call


class TestARIHelpers(TestCase):

    @patch('wazo_calld.plugins.transfers.ari_helpers.ami')
    def test_given_amid_unreachable_when_hold_transferred_call_then_silence(self, ami_helpers):
        ari = Mock()
        amid = Mock()
        ami_helpers.moh_class_exists.side_effect = WazoAmidError(Mock(), Mock())
        transferred_call = sentinel.transferred

        hold_transferred_call(ari, amid, transferred_call)

        assert_that(ari.channels.startMoh.called, is_(False))
        ari.channels.startSilence.assert_called_once_with(channelId=transferred_call)

    @patch('wazo_calld.plugins.transfers.ari_helpers.ami')
    def test_given_moh_does_not_exist_when_hold_transferred_call_then_silence(self, ami_helpers):
        ari = Mock()
        amid = Mock()
        ami_helpers.moh_class_exists.return_value = False
        transferred_call = sentinel.transferred

        hold_transferred_call(ari, amid, transferred_call)

        assert_that(ari.channels.startMoh.called, is_(False))
        ari.channels.startSilence.assert_called_once_with(channelId=transferred_call)

    @patch('wazo_calld.plugins.transfers.ari_helpers.ami')
    def test_given_moh_exists_when_hold_transferred_call_then_silence(self, ami_helpers):
        ari = Mock()
        amid = Mock()
        ami_helpers.moh_class_exists.return_value = True
        transferred_call = sentinel.transferred

        hold_transferred_call(ari, amid, transferred_call)

        assert_that(ari.channels.startSilence.called, is_(False))
        ari.channels.startMoh.assert_called_once_with(channelId=transferred_call, mohClass='default')
