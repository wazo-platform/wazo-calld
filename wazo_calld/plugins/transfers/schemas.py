# Copyright 2016-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import Schema, fields, post_load
from marshmallow.validate import OneOf, Length

from wazo_calld.plugin_helpers.mallow import StrictDict


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

    @post_load
    def remove_extension_whitespace(self, call_request, **kwargs):
        call_request['exten'] = ''.join(call_request['exten'].split())
        return call_request


transfer_request_schema = TransferRequestSchema()


class UserTransferRequestSchema(Schema):
    initiator_call = fields.Str(validate=Length(min=1), required=True)
    exten = fields.Str(validate=Length(min=1), required=True)
    flow = fields.Str(validate=OneOf(['attended', 'blind']), missing='attended')
    timeout = fields.Integer(missing=None, min=1, allow_none=True)

    @post_load
    def remove_extension_whitespace(self, call_request, **kwargs):
        call_request['exten'] = ''.join(call_request['exten'].split())
        return call_request


user_transfer_request_schema = UserTransferRequestSchema()
