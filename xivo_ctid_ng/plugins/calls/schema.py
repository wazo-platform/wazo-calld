# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from marshmallow import Schema, fields, post_dump
from marshmallow.validate import Length
from marshmallow.validate import Range

from xivo_ctid_ng.helpers.mallow import StrictDict


class CallRequestSourceSchema(Schema):
    from_mobile = fields.Boolean(missing=False)
    line_id = fields.Integer()
    user = fields.String(required=True)


class CallRequestDestinationSchema(Schema):
    context = fields.String(validate=Length(min=1), required=True)
    extension = fields.String(validate=Length(min=1), required=True)
    priority = fields.Integer(validate=Range(min=1), required=True)


class CallRequestSchema(Schema):
    source = fields.Nested('CallRequestSourceSchema', required=True)
    destination = fields.Nested('CallRequestDestinationSchema', required=True)
    variables = StrictDict(key_field=fields.String(required=True, validate=Length(min=1)),
                           value_field=fields.String(required=True, validate=Length(min=1)),
                           missing=dict)


class UserCallRequestSchema(Schema):
    extension = fields.String(validate=Length(min=1), required=True)
    line_id = fields.Integer()
    from_mobile = fields.Boolean(missing=False)
    variables = StrictDict(key_field=fields.String(required=True, validate=Length(min=1)),
                           value_field=fields.String(required=True, validate=Length(min=1)),
                           missing=dict)


class CallSchema(Schema):
    bridges = fields.List(fields.String())
    call_id = fields.String(attribute='id_')
    caller_id_name = fields.String()
    caller_id_number = fields.String()
    peer_caller_id_name = fields.String()
    peer_caller_id_number = fields.String()
    creation_time = fields.String()
    status = fields.String()
    on_hold = fields.Boolean()
    talking_to = StrictDict(key_field=fields.String(), value_field=fields.String())
    user_uuid = fields.String()
    is_caller = fields.Boolean()
    dialed_extension = fields.String()

    @post_dump()
    def default_peer_caller_id_number(self, call):
        if call['peer_caller_id_number'] == '':
            call['peer_caller_id_number'] = call['dialed_extension']


call_schema = CallSchema()
