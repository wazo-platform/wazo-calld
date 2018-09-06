# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from marshmallow import Schema, fields, pre_load
from xivo.mallow.validate import Length
from xivo_ctid_ng.helpers.mallow import StrictDict


class BaseSchema(Schema):
    class Meta:
        strict = True

    @pre_load
    def ensure_dict(self, data):
        return data or {}


class ApplicationCallRequestSchema(BaseSchema):
    exten = fields.String(validate=Length(min=1), required=True)
    context = fields.String(required=True)
    autoanswer = fields.Boolean(required=False, missing=False)


class ApplicationCallSchema(BaseSchema):
    id = fields.String(attribute='id_')
    caller_id_name = fields.String()
    caller_id_number = fields.String()
    creation_time = fields.String()
    status = fields.String()
    on_hold = fields.Boolean()
    is_caller = fields.Boolean()
    dialed_extension = fields.String()
    variables = StrictDict(key_field=fields.String(), value_field=fields.String())
    node_uuid = fields.String()


class ApplicationNodeCallSchema(BaseSchema):
    id = fields.String(attribute='id_', required=True)


class ApplicationNodeSchema(BaseSchema):
    uuid = fields.String(dump_only=True)
    calls = fields.Nested(ApplicationNodeCallSchema, many=True, validate=Length(min=1), required=True)


class ApplicationSchema(Schema):
    destination_node_uuid = fields.String()


application_call_request_schema = ApplicationCallRequestSchema()
application_call_schema = ApplicationCallSchema()
application_node_schema = ApplicationNodeSchema()
application_schema = ApplicationSchema()
