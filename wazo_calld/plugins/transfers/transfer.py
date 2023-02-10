# Copyright 2016-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later


class Transfer:
    def __init__(self, id_, initiator_uuid, initiator_tenant_uuid):
        self.id = id_
        self.initiator_uuid = initiator_uuid
        self.initiator_tenant_uuid = initiator_tenant_uuid
        self.transferred_call = None
        self.initiator_call = None
        self.recipient_call = None
        self.status = 'invalid'
        self.flow = 'attended'

    def to_dict(self):
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

    @classmethod
    def from_dict(cls, dict_):
        transfer = cls(
            dict_['id'],
            dict_['initiator_uuid'],
            dict_['initiator_tenant_uuid'],
        )
        transfer.transferred_call = dict_['transferred_call']
        transfer.initiator_call = dict_['initiator_call']
        transfer.recipient_call = dict_['recipient_call']
        transfer.status = dict_['status']
        transfer.flow = dict_['flow']
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
