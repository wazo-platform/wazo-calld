# Copyright 2016-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from flask import request

from wazo_calld.auth import get_token_user_uuid_from_request, required_acl
from wazo_calld.http import AuthResource

from .schemas import transfer_request_schema, user_transfer_request_schema


class TransfersResource(AuthResource):
    def __init__(self, transfers_service):
        self._transfers_service = transfers_service

    @required_acl('calld.transfers.create')
    def post(self):
        request_body = transfer_request_schema.load(request.get_json(force=True))
        transfer = self._transfers_service.create(
            request_body['transferred_call'],
            request_body['initiator_call'],
            request_body['context'],
            request_body['exten'],
            request_body['flow'],
            request_body['variables'],
            request_body['timeout'],
        )
        return transfer.to_public_dict(), 201


class UserTransfersResource(AuthResource):
    def __init__(self, transfers_service):
        self._transfers_service = transfers_service

    @required_acl('calld.users.me.transfers.read')
    def get(self):
        user_uuid = get_token_user_uuid_from_request()
        transfers = self._transfers_service.list_from_user(user_uuid)

        return {'items': [transfer.to_public_dict() for transfer in transfers]}, 200

    @required_acl('calld.users.me.transfers.create')
    def post(self):
        request_body = user_transfer_request_schema.load(request.get_json(force=True))
        user_uuid = get_token_user_uuid_from_request()
        transfer = self._transfers_service.create_from_user(
            request_body['initiator_call'],
            request_body['exten'],
            request_body['flow'],
            request_body['timeout'],
            user_uuid,
        )
        return transfer.to_public_dict(), 201


class TransferResource(AuthResource):
    def __init__(self, transfers_service):
        self._transfers_service = transfers_service

    @required_acl('calld.transfers.{transfer_id}.read')
    def get(self, transfer_id):
        transfer = self._transfers_service.get(transfer_id)
        return transfer.to_public_dict(), 200

    @required_acl('calld.transfers.{transfer_id}.delete')
    def delete(self, transfer_id):
        self._transfers_service.cancel(transfer_id)
        return '', 204


class UserTransferResource(AuthResource):
    def __init__(self, transfers_service):
        self._transfers_service = transfers_service

    @required_acl('calld.users.me.transfers.{transfer_id}.delete')
    def delete(self, transfer_id):
        user_uuid = get_token_user_uuid_from_request()
        self._transfers_service.cancel_from_user(transfer_id, user_uuid)
        return '', 204


class TransferCompleteResource(AuthResource):
    def __init__(self, transfers_service):
        self._transfers_service = transfers_service

    @required_acl('calld.transfers.{transfer_id}.complete.update')
    def put(self, transfer_id):
        self._transfers_service.complete(transfer_id)
        return '', 204


class UserTransferCompleteResource(AuthResource):
    def __init__(self, transfers_service):
        self._transfers_service = transfers_service

    @required_acl('calld.users.me.transfers.{transfer_id}.complete.update')
    def put(self, transfer_id):
        user_uuid = get_token_user_uuid_from_request()
        self._transfers_service.complete_from_user(transfer_id, user_uuid)
        return '', 204
