# Copyright 2019-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import post_load

from xivo.mallow import fields
from xivo.mallow_helpers import Schema


class FaxCreationRequestSchema(Schema):
    context = fields.String(required=True)
    extension = fields.String(required=True)
    caller_id = fields.String(missing='Wazo Fax')

    @post_load
    def remove_extension_whitespace(self, call_request):
        call_request['extension'] = ''.join(call_request['extension'].split())
        return call_request


class UserFaxCreationRequestSchema(Schema):
    extension = fields.String(required=True)
    caller_id = fields.String(missing='Wazo Fax')

    @post_load
    def remove_extension_whitespace(self, call_request):
        call_request['extension'] = ''.join(call_request['extension'].split())
        return call_request


class FaxSchema(Schema):
    id = fields.String(dump_only=True)
    call_id = fields.String(dump_only=True)
    context = fields.String(required=True)
    extension = fields.String(required=True)
    caller_id = fields.String(missing='Wazo Fax')
    user_uuid = fields.String(dump_only=True)
    tenant_uuid = fields.String(dump_only=True)


fax_creation_request_schema = FaxCreationRequestSchema()
user_fax_creation_request_schema = UserFaxCreationRequestSchema()
fax_schema = FaxSchema()
