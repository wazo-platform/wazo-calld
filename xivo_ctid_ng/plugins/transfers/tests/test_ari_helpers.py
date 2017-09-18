# -*- coding: utf-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import is_
from mock import Mock
from mock import patch
from mock import sentinel
from unittest import TestCase

from xivo_ctid_ng.exceptions import XiVOAmidError

from ..ari_helpers import hold_transferred_call


class TestARIHelpers(TestCase):

    @patch('xivo_ctid_ng.plugins.transfers.ari_helpers.ami')
    def test_given_amid_unreachable_when_hold_transferred_call_then_silence(self, ami_helpers):
        ari = Mock()
        amid = Mock()
        ami_helpers.moh_class_exists.side_effect = XiVOAmidError(Mock(), Mock())
        transferred_call = sentinel.transferred

        hold_transferred_call(ari, amid, transferred_call)

        assert_that(ari.channels.startMoh.called, is_(False))
        ari.channels.startSilence.assert_called_once_with(channelId=transferred_call)

    @patch('xivo_ctid_ng.plugins.transfers.ari_helpers.ami')
    def test_given_moh_does_not_exist_when_hold_transferred_call_then_silence(self, ami_helpers):
        ari = Mock()
        amid = Mock()
        ami_helpers.moh_class_exists.return_value = False
        transferred_call = sentinel.transferred

        hold_transferred_call(ari, amid, transferred_call)

        assert_that(ari.channels.startMoh.called, is_(False))
        ari.channels.startSilence.assert_called_once_with(channelId=transferred_call)

    @patch('xivo_ctid_ng.plugins.transfers.ari_helpers.ami')
    def test_given_moh_exists_when_hold_transferred_call_then_silence(self, ami_helpers):
        ari = Mock()
        amid = Mock()
        ami_helpers.moh_class_exists.return_value = True
        transferred_call = sentinel.transferred

        hold_transferred_call(ari, amid, transferred_call)

        assert_that(ari.channels.startSilence.called, is_(False))
        ari.channels.startMoh.assert_called_once_with(channelId=transferred_call, mohClass='default')
