# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from flask import request
from marshmallow import Schema, fields
from marshmallow.validate import OneOf, Length, Range

from xivo_ctid_ng.auth import get_token_user_uuid_from_request
from xivo_ctid_ng.auth import required_acl
from xivo_ctid_ng.rest_api import AuthResource


class LineLocationSchema(Schema):
    line_id = fields.Integer(validate=Range(min=1), required=True)


class LocationField(fields.Field):

    _locations = {
        'line': fields.Nested(LineLocationSchema),
    }

    def _deserialize(self, value, attr, data):
        method = data.get('destination')
        concrete_location = self._locations.get(method)
        if not concrete_location:
            return {}
        return concrete_location._deserialize(value, attr, data)


class UserRelocateRequestSchema(Schema):
    initiator_call = fields.Str(validate=Length(min=1), required=True)
    destination = fields.Str(validate=OneOf('line'))
    location = LocationField(missing=dict)


user_relocate_request_schema = UserRelocateRequestSchema(strict=True)


class RelocateSchema(Schema):
    uuid = fields.Str(validate=Length(equal=36), required=True)
    relocated_call = fields.Str(validate=Length(min=1), required=True, attribute='relocated_channel')
    initiator_call = fields.Str(validate=Length(min=1), required=True, attribute='initiator_channel')
    recipient_call = fields.Str(validate=Length(min=1), required=True, attribute='recipient_channel')

    class Meta:
        strict = True


relocate_schema = RelocateSchema()


class UserRelocatesResource(AuthResource):

    def __init__(self, auth_client, relocates_service):
        self._auth_client = auth_client
        self._relocates_service = relocates_service

    @required_acl('ctid-ng.users.me.relocates.read')
    def get(self):
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        relocates = self._relocates_service.list_from_user(user_uuid)

        return {
            'items': [relocate.to_dict() for relocate in relocates]
        }, 200

    @required_acl('ctid-ng.users.me.relocates.create')
    def post(self):
        request_body = user_relocate_request_schema.load(request.get_json(force=True)).data
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        relocate = self._relocates_service.create_from_user(request_body['initiator_call'],
                                                            request_body['destination'],
                                                            request_body['location'],
                                                            user_uuid)
        result = relocate_schema.dump(relocate).data
        return result, 201
