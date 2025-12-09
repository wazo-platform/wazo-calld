# Copyright 2016-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Literal
from uuid import uuid4

InternalTransferStatus = Literal[
    'none_moved_to_stasis',
    'none_moved_to_stasis_cancelled',
    'initiator_moved_to_stasis',
    'initiator_moved_to_stasis_cancelled',
    'transferred_moved_to_stasis',
    'transferred_moved_to_stasis_cancelled',
    'starting',
    'invalid',
    'answered',
    'blind_transferred',
    'ringback',
    'ready',
    'starting',
    'non_stasis',
    'ended',
    'abandoned',
]
FlowType = Literal['attended', 'blind']


class Transfer:
    def __init__(
        self,
        initiator_uuid: str,
        initiator_tenant_uuid: str,
        initiator_call: str,
        transferred_call: str,
        id_: str | None = None,
        recipient_call: str | None = None,
        flow: FlowType = 'attended',
        transfer_bridge_id: str | None = None,
    ):
        self.id: str = id_ or str(uuid4())
        self.initiator_uuid: str = initiator_uuid
        self.initiator_tenant_uuid: str = initiator_tenant_uuid
        self.transferred_call: str = transferred_call
        self.initiator_call: str = initiator_call
        self.recipient_call: str | None = recipient_call
        self.transfer_bridge_id: str = transfer_bridge_id or self.id
        self.status: InternalTransferStatus = 'invalid'
        self.flow: FlowType = flow

    def to_internal_dict(self):
        return {
            'id': self.id,
            'initiator_uuid': self.initiator_uuid,
            'initiator_tenant_uuid': self.initiator_tenant_uuid,
            'transferred_call': self.transferred_call,
            'initiator_call': self.initiator_call,
            'recipient_call': self.recipient_call,
            'transfer_bridge_id': self.transfer_bridge_id,
            'status': self.status,
            'flow': self.flow,
        }

    def to_public_dict(self):
        return {
            'id': self.id,
            'initiator_uuid': self.initiator_uuid,
            'initiator_tenant_uuid': self.initiator_tenant_uuid,
            'transferred_call': self.transferred_call,
            'initiator_call': self.initiator_call,
            'recipient_call': self.recipient_call,
            'status': self.public_status(),
            'flow': self.flow,
        }

    def public_status(self):
        # we don't want to expose stasis-related statuses
        if self.status in (
            'none_moved_to_stasis',
            'initiator_moved_to_stasis',
            'transferred_moved_to_stasis',
        ):
            return 'starting'
        elif self.status in (
            'none_moved_to_stasis_cancelled',
            'initiator_moved_to_stasis_cancelled',
            'transferred_moved_to_stasis_cancelled',
        ):
            return 'abandoned'
        return self.status

    @classmethod
    def from_dict(cls, dict_):
        transfer = cls(
            id_=dict_['id'],
            initiator_uuid=dict_['initiator_uuid'],
            initiator_tenant_uuid=dict_['initiator_tenant_uuid'],
            transferred_call=dict_['transferred_call'],
            initiator_call=dict_['initiator_call'],
            recipient_call=dict_['recipient_call'],
            flow=dict_['flow'],
            transfer_bridge_id=dict_['transfer_bridge_id'],
        )
        transfer.status = dict_['status']
        return transfer

    def role(self, call_id):
        if call_id == self.transferred_call:
            return TransferRole.transferred
        elif call_id == self.initiator_call:
            return TransferRole.initiator
        elif call_id == self.recipient_call:
            return TransferRole.recipient
        else:
            raise KeyError(call_id)


class TransferStatus:
    answered: Literal['answered'] = 'answered'
    blind_transferred: Literal['blind_transferred'] = 'blind_transferred'
    ringback: Literal['ringback'] = 'ringback'
    ready: Literal['ready'] = 'ready'
    starting: Literal['starting'] = 'starting'
    abandoned: Literal['abandoned'] = 'abandoned'


TransferRoleType = Literal['transferred', 'initiator', 'recipient']


class TransferRole:
    transferred: Literal['transferred'] = 'transferred'
    initiator: Literal['initiator'] = 'initiator'
    recipient: Literal['recipient'] = 'recipient'
