# Copyright 2016-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Literal
from uuid import uuid4


class Transfer:
    def __init__(
        self,
        initiator_uuid: str,
        initiator_tenant_uuid: str,
        id_: str | None = None,
        initiator_call: str | None = None,
        transferred_call: str | None = None,
        recipient_call: str | None = None,
        flow: Literal['attended', 'blind'] = 'attended',
    ):
        self.id = id_ or str(uuid4())
        self.initiator_uuid = initiator_uuid
        self.initiator_tenant_uuid = initiator_tenant_uuid
        self.transferred_call = transferred_call
        self.initiator_call = initiator_call
        self.recipient_call = recipient_call
        self.status = 'invalid'
        self.flow = flow

    def to_internal_dict(self):
        return {
            'id': self.id,
            'initiator_uuid': self.initiator_uuid,
            'initiator_tenant_uuid': self.initiator_tenant_uuid,
            'transferred_call': self.transferred_call,
            'initiator_call': self.initiator_call,
            'recipient_call': self.recipient_call,
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
    answered = 'answered'
    blind_transferred = 'blind_transferred'
    ringback = 'ringback'
    ready = 'ready'
    starting = 'starting'


class TransferRole:
    transferred = 'transferred'
    initiator = 'initiator'
    recipient = 'recipient'
