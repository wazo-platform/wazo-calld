# Copyright 2016-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import EXCLUDE, Schema, fields, post_dump, post_load
from marshmallow.validate import Length, Range, Regexp

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

    @post_load
    def remove_extension_whitespace(self, call_request, **kwargs):
        call_request['extension'] = ''.join(call_request['extension'].split())
        return call_request


class CallRequestSchema(CallBaseSchema):
    source = fields.Nested('CallRequestSourceSchema', required=True)
    destination = fields.Nested('CallRequestDestinationSchema', required=True)
    variables = StrictDict(
        key_field=fields.String(required=True, validate=Length(min=1)),
        value_field=fields.String(required=True, validate=Length(min=1)),
        missing=dict,
    )


class UserCallRequestSchema(CallBaseSchema):
    extension = fields.String(validate=Length(min=1), required=True)
    line_id = fields.Integer()
    all_lines = fields.Boolean(missing=False)
    from_mobile = fields.Boolean(missing=False)
    variables = StrictDict(
        key_field=fields.String(required=True, validate=Length(min=1)),
        value_field=fields.String(required=True, validate=Length(min=1)),
        missing=dict,
    )
    auto_answer_caller = fields.Boolean(missing=False)

    @post_load
    def remove_extension_whitespace(self, call_request, **kwargs):
        call_request['extension'] = ''.join(call_request['extension'].split())
        return call_request


class CallDtmfSchema(CallBaseSchema):
    digits = fields.String(validate=Regexp(r'^[0-9*#]+$'), required=True)


class CallSchema(CallBaseSchema):
    bridges = fields.List(fields.String())
    call_id = fields.String(attribute='id_')
    caller_id_name = fields.String()
    caller_id_number = fields.String()
    conversation_id = fields.String()
    peer_caller_id_name = fields.String()
    peer_caller_id_number = fields.String()
    creation_time = fields.String()
    status = fields.String()
    on_hold = fields.Boolean()
    muted = fields.Boolean()
    record_state = fields.String()
    talking_to = StrictDict(key_field=fields.String(), value_field=fields.String())
    user_uuid = fields.String()
    is_caller = fields.Boolean()
    is_video = fields.Boolean()
    dialed_extension = fields.String()
    sip_call_id = fields.String()
    line_id = fields.Integer()
    answer_time = fields.String()
    hangup_time = fields.String()
    direction = fields.String()
    parked = fields.Boolean()

    @post_dump()
    def default_peer_caller_id_number(self, call, **kwargs):
        if call['peer_caller_id_number'] == '':
            call['peer_caller_id_number'] = call['dialed_extension']
        return call


class ConnectCallRequestBodySchema(CallBaseSchema):
    timeout = fields.Integer(
        validate=Range(min=0),
        missing=30,
        allow_none=True,
    )


connect_call_request_body_schema = ConnectCallRequestBodySchema()

call_schema = CallSchema()
