# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from flask import request
from marshmallow import Schema, fields
from marshmallow.validate import OneOf, Length

from xivo_ctid_ng.auth import get_token_user_uuid_from_request
from xivo_ctid_ng.auth import required_acl
from xivo_ctid_ng.rest_api import AuthResource
from xivo_ctid_ng.helpers.mallow import StrictDict


class TransferRequestSchema(Schema):
    transferred_call = fields.Str(validate=Length(min=1), required=True)
    initiator_call = fields.Str(validate=Length(min=1), required=True)
    context = fields.Str(validate=Length(min=1), required=True)
    exten = fields.Str(validate=Length(min=1), required=True)
    flow = fields.Str(validate=OneOf(['attended', 'blind']), missing='attended')
    variables = StrictDict(key_field=fields.String(required=True, validate=Length(min=1)),
                           value_field=fields.String(required=True, validate=Length(min=1)),
                           missing=dict)
    timeout = fields.Integer(missing=None, min=1, allow_none=True)

transfer_request_schema = TransferRequestSchema(strict=True)


class UserTransferRequestSchema(Schema):
    initiator_call = fields.Str(validate=Length(min=1), required=True)
    exten = fields.Str(validate=Length(min=1), required=True)
    flow = fields.Str(validate=OneOf(['attended', 'blind']), missing='attended')
    timeout = fields.Integer(missing=None, min=1, allow_none=True)

user_transfer_request_schema = UserTransferRequestSchema(strict=True)


class TransfersResource(AuthResource):

    def __init__(self, transfers_service):
        self._transfers_service = transfers_service

    @required_acl('ctid-ng.transfers.create')
    def post(self):
        request_body = transfer_request_schema.load(request.get_json(force=True)).data
        transfer = self._transfers_service.create(request_body['transferred_call'],
                                                  request_body['initiator_call'],
                                                  request_body['context'],
                                                  request_body['exten'],
                                                  request_body['flow'],
                                                  request_body['variables'],
                                                  request_body['timeout'])
        return transfer.to_dict(), 201


class UserTransfersResource(AuthResource):

    def __init__(self, auth_client, transfers_service):
        self._auth_client = auth_client
        self._transfers_service = transfers_service

    @required_acl('ctid-ng.users.me.transfers.read')
    def get(self):
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        transfers = self._transfers_service.list_from_user(user_uuid)

        return {
            'items': [transfer.to_dict() for transfer in transfers]
        }, 200

    @required_acl('ctid-ng.users.me.transfers.create')
    def post(self):
        request_body = user_transfer_request_schema.load(request.get_json(force=True)).data
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        transfer = self._transfers_service.create_from_user(request_body['initiator_call'],
                                                            request_body['exten'],
                                                            request_body['flow'],
                                                            request_body['timeout'],
                                                            user_uuid)
        return transfer.to_dict(), 201


class TransferResource(AuthResource):

    def __init__(self, transfers_service):
        self._transfers_service = transfers_service

    @required_acl('ctid-ng.transfers.{transfer_id}.read')
    def get(self, transfer_id):
        transfer = self._transfers_service.get(transfer_id)
        return transfer.to_dict(), 200

    @required_acl('ctid-ng.transfers.{transfer_id}.delete')
    def delete(self, transfer_id):
        self._transfers_service.cancel(transfer_id)
        return '', 204


class UserTransferResource(AuthResource):

    def __init__(self, auth_client, transfers_service):
        self._auth_client = auth_client
        self._transfers_service = transfers_service

    @required_acl('ctid-ng.users.me.transfers.{transfer_id}.delete')
    def delete(self, transfer_id):
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        self._transfers_service.cancel_from_user(transfer_id, user_uuid)
        return '', 204


class TransferCompleteResource(AuthResource):

    def __init__(self, transfers_service):
        self._transfers_service = transfers_service

    @required_acl('ctid-ng.transfers.{transfer_id}.complete.update')
    def put(self, transfer_id):
        self._transfers_service.complete(transfer_id)
        return '', 204


class UserTransferCompleteResource(AuthResource):

    def __init__(self, auth_client, transfers_service):
        self._auth_client = auth_client
        self._transfers_service = transfers_service

    @required_acl('ctid-ng.users.me.transfers.{transfer_id}.complete.update')
    def put(self, transfer_id):
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        self._transfers_service.complete_from_user(transfer_id, user_uuid)
        return '', 204
