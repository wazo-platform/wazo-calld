# Copyright 2016-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging

from xivo_bus.resources.calls.transfer import (AbandonTransferEvent,
                                               AnswerTransferEvent,
                                               CancelTransferEvent,
                                               CompleteTransferEvent,
                                               CreateTransferEvent,
                                               EndTransferEvent,
                                               UpdateTransferEvent,)

logger = logging.getLogger(__name__)


class TransferNotifier:

    def __init__(self, bus_producer):
        self._bus_producer = bus_producer

    @staticmethod
    def _build_headers(user_uuids=None, **kwargs):
        headers = {}
        for uuid in user_uuids or []:
            headers[f'user_uuid:{uuid}'] = True

        for key, value in kwargs.items():
            if value:
                headers[key] = value
        return headers

    def created(self, transfer):
        event = CreateTransferEvent(transfer.initiator_uuid, transfer.to_dict())
        headers = self._build_headers(
            user_uuids=[transfer.initiator_uuid],
            tenant_uuid=transfer.initiator_tenant_uuid,
        )
        self._bus_producer.publish(event, headers=headers)

    def updated(self, transfer):
        event = UpdateTransferEvent(transfer.initiator_uuid, transfer.to_dict())
        headers = self._build_headers(
            user_uuids=[transfer.initiator_uuid],
            tenant_uuid=transfer.initiator_tenant_uuid,
        )
        self._bus_producer.publish(event, headers=headers)

    def answered(self, transfer):
        event = AnswerTransferEvent(transfer.initiator_uuid, transfer.to_dict())
        headers = self._build_headers(
            user_uuids=[transfer.initiator_uuid],
            tenant_uuid=transfer.initiator_tenant_uuid,
        )
        self._bus_producer.publish(event, headers=headers)

    def cancelled(self, transfer):
        event = CancelTransferEvent(transfer.initiator_uuid, transfer.to_dict())
        headers = self._build_headers(
            user_uuids=[transfer.initiator_uuid],
            tenant_uuid=transfer.initiator_tenant_uuid,
        )
        self._bus_producer.publish(event, headers=headers)

    def completed(self, transfer):
        event = CompleteTransferEvent(transfer.initiator_uuid, transfer.to_dict())
        headers = self._build_headers(
            user_uuids=[transfer.initiator_uuid],
            tenant_uuid=transfer.initiator_tenant_uuid,
        )
        self._bus_producer.publish(event, headers=headers)

    def abandoned(self, transfer):
        event = AbandonTransferEvent(transfer.initiator_uuid, transfer.to_dict())
        headers = self._build_headers(
            user_uuids=[transfer.initiator_uuid],
            tenant_uuid=transfer.initiator_tenant_uuid,
        )
        self._bus_producer.publish(event, headers=headers)

    def ended(self, transfer):
        event = EndTransferEvent(transfer.initiator_uuid, transfer.to_dict())
        headers = self._build_headers(
            user_uuids=[transfer.initiator_uuid],
            tenant_uuid=transfer.initiator_tenant_uuid,
        )
        self._bus_producer.publish(event, headers=headers)
