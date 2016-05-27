# -*- coding: utf-8 -*-
# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from hamcrest import assert_that
from hamcrest import calling
from hamcrest import equal_to
from hamcrest import raises
from unittest import TestCase

from ..transfer import Transfer, TransferRole


class Testclassname(TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_transfer_role(self):
        transfer = Transfer('id')
        transfer.transferred_call = 'transferred'
        transfer.initiator_call = 'initiator'
        transfer.recipient_call = 'recipient'

        assert_that(transfer.role(transfer.transferred_call), equal_to(TransferRole.transferred))
        assert_that(transfer.role(transfer.initiator_call), equal_to(TransferRole.initiator))
        assert_that(transfer.role(transfer.recipient_call), equal_to(TransferRole.recipient))
        assert_that(calling(transfer.role).with_args('unknown'), raises(KeyError))
