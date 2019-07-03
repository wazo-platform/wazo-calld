# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import (
    Schema,
    fields,
    pre_dump,
    pre_load,
    post_load,
)
from xivo.mallow.validate import (
    Length,
    OneOf,
    validate_string_dict,
)
from wazo_calld.helpers.mallow import StrictDict


class BaseSchema(Schema):
    class Meta:
        strict = True

    @pre_load
    def ensure_dict(self, data):
        return data or {}


class ApplicationCallPlaySchema(BaseSchema):
    uuid = fields.String(attribute='id', dump_only=True)
    uri = fields.String(attribute='media_uri', required=True)
    language = fields.String()


class ApplicationCallRequestSchema(BaseSchema):
    exten = fields.String(validate=Length(min=1), required=True)
    context = fields.String(required=True)
    autoanswer = fields.Boolean(required=False, missing=False)
    variables = fields.Dict(validate=validate_string_dict, missing={})
    displayed_caller_id_name = fields.String(missing='', validate=Length(max=256))
    displayed_caller_id_number = fields.String(missing='', validate=Length(max=256))


class ApplicationCallUserRequestSchema(BaseSchema):
    user_uuid = fields.String(required=True)
    autoanswer = fields.Boolean(required=False, missing=False)
    variables = fields.Dict(validate=validate_string_dict, missing={})
    displayed_caller_id_name = fields.String(missing='', validate=Length(max=256))
    displayed_caller_id_number = fields.String(missing='', validate=Length(max=256))


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
    moh_uuid = fields.String()
    muted = fields.Boolean()
    snoops = fields.Dict(dump_only=True)


class ApplicationNodeCallSchema(BaseSchema):
    id = fields.String(attribute='id_', required=True)


class ApplicationNodeSchema(BaseSchema):
    uuid = fields.String(dump_only=True)
    calls = fields.Nested(ApplicationNodeCallSchema, many=True, validate=Length(min=1), required=True)


class ApplicationSnoopPutSchema(BaseSchema):
    whisper_mode = fields.String(validate=OneOf(['in', 'out', 'both']), missing=None)

    @post_load
    def load_whisper_mode(self, data):
        whisper_mode = data.get('whisper_mode')
        if whisper_mode is None:
            data['whisper_mode'] = 'none'
        return data

    @pre_dump
    def dump_whisper_mode(self, data):
        if data.whisper_mode == 'none':
            data.whisper_mode = None
        return data


class ApplicationSnoopSchema(ApplicationSnoopPutSchema):
    uuid = fields.String(dump_only=True)
    snooped_call_id = fields.String(dump_only=True)
    snooping_call_id = fields.String(required=True)
    # whisper_mode from parent


class ApplicationSchema(Schema):
    destination_node_uuid = fields.String()


application_call_request_schema = ApplicationCallRequestSchema()
application_call_user_request_schema = ApplicationCallUserRequestSchema()
application_call_schema = ApplicationCallSchema()
application_node_schema = ApplicationNodeSchema()
application_playback_schema = ApplicationCallPlaySchema()
application_schema = ApplicationSchema()
application_snoop_schema = ApplicationSnoopSchema()
application_snoop_put_schema = ApplicationSnoopPutSchema()
