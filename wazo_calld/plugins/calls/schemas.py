# Copyright 2016-2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import EXCLUDE, Schema, fields, post_dump
from marshmallow.validate import Length
from marshmallow.validate import Range
from marshmallow.validate import Regexp

from wazo_calld.plugin_helpers.mallow import StrictDict


class CallBaseSchema(Schema):
    class Meta:
        unknown = EXCLUDE


class CallRequestSourceSchema(CallBaseSchema):
    from_mobile = fields.Boolean(missing=False)
    line_id = fields.Integer()
    all_lines = fields.Boolean(missing=False)
    user = fields.String(required=True)
    auto_answer = fields.Boolean(missing=False)


class CallRequestDestinationSchema(CallBaseSchema):
    context = fields.String(validate=Length(min=1), required=True)
    extension = fields.String(validate=Length(min=1), required=True)
    priority = fields.Integer(validate=Range(min=1), required=True)


class CallRequestSchema(CallBaseSchema):
    source = fields.Nested('CallRequestSourceSchema', required=True,
                           unknown=EXCLUDE)
    destination = fields.Nested('CallRequestDestinationSchema', required=True,
                                unknown=EXCLUDE)
    variables = StrictDict(key_field=fields.String(required=True, validate=Length(min=1)),
                           value_field=fields.String(required=True, validate=Length(min=1)),
                           missing=dict)


class UserCallRequestSchema(CallBaseSchema):
    extension = fields.String(validate=Length(min=1), required=True)
    line_id = fields.Integer()
    all_lines = fields.Boolean(missing=False)
    from_mobile = fields.Boolean(missing=False)
    variables = StrictDict(key_field=fields.String(required=True, validate=Length(min=1)),
                           value_field=fields.String(required=True, validate=Length(min=1)),
                           missing=dict)
    auto_answer_caller = fields.Boolean(missing=False)


class CallDtmfSchema(CallBaseSchema):
    digits = fields.String(validate=Regexp(r'^[0-9*#]+$'))


class CallSchema(CallBaseSchema):
    bridges = fields.List(fields.String())
    call_id = fields.String(attribute='id_')
    caller_id_name = fields.String()
    caller_id_number = fields.String()
    peer_caller_id_name = fields.String()
    peer_caller_id_number = fields.String()
    creation_time = fields.String()
    status = fields.String()
    on_hold = fields.Boolean()
    muted = fields.Boolean()
    talking_to = StrictDict(key_field=fields.String(), value_field=fields.String())
    user_uuid = fields.String()
    is_caller = fields.Boolean()
    dialed_extension = fields.String()
    sip_call_id = fields.String()

    @post_dump()
    def default_peer_caller_id_number(self, call):
        if call['peer_caller_id_number'] == '':
            call['peer_caller_id_number'] = call['dialed_extension']
        return call


call_schema = CallSchema()
