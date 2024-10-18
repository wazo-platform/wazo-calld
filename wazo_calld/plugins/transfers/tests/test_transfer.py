# Copyright 2016-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest import TestCase

from hamcrest import assert_that, calling, equal_to, raises

from ..transfer import Transfer, TransferRole


class TestTransfer(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_create_transfer_with_defaults(self):
        transfer = Transfer(
            initiator_uuid='initiator_uuid',
            initiator_tenant_uuid='initiator_tenant_uuid',
            transferred_call='transferred',
            initiator_call='initiator',
        )
        assert transfer.id and isinstance(transfer.id, str)
        assert transfer.flow == 'attended'

    def test_transfer_role(self):
        transfer = Transfer(
            id_='id',
            initiator_uuid='initiator_uuid',
            initiator_tenant_uuid='initiator_tenant_uuid',
            transferred_call='transferred',
            initiator_call='initiator',
            recipient_call='recipient',
        )

        assert_that(
            transfer.role(transfer.transferred_call), equal_to(TransferRole.transferred)
        )
        assert_that(
            transfer.role(transfer.initiator_call), equal_to(TransferRole.initiator)
        )
        assert_that(
            transfer.role(transfer.recipient_call), equal_to(TransferRole.recipient)
        )
        assert_that(calling(transfer.role).with_args('unknown'), raises(KeyError))
