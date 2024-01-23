# Copyright 2018-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import EXCLUDE, Schema, fields, post_load, pre_load
from xivo.mallow.validate import Length, OneOf, Regexp, validate_string_dict

from wazo_calld.plugin_helpers.mallow import StrictDict


class BaseSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    @pre_load
    def ensure_dict(self, data, **kwargs):
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

    @post_load
    def remove_extension_whitespace(self, call_request, **kwargs):
        call_request['exten'] = ''.join(call_request['exten'].split())
        return call_request


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
    user_uuid = fields.String()
    tenant_uuid = fields.String()


class ApplicationNodeCallSchema(BaseSchema):
    id = fields.String(attribute='id_', required=True)


class ApplicationNodeSchema(BaseSchema):
    uuid = fields.String(dump_only=True)
    calls = fields.Nested(
        ApplicationNodeCallSchema, many=True, validate=Length(min=1), required=True
    )


class ApplicationSnoopPutSchema(BaseSchema):
    whisper_mode = fields.String(
        validate=OneOf(['in', 'out', 'both', 'none']), missing='none'
    )


class ApplicationSnoopSchema(ApplicationSnoopPutSchema):
    uuid = fields.String(dump_only=True)
    snooped_call_id = fields.String(dump_only=True)
    snooping_call_id = fields.String(required=True)
    # whisper_mode from parent


class ApplicationSchema(Schema):
    destination_node_uuid = fields.String()


class ApplicationDTMFSchema(BaseSchema):
    digits = fields.String(validate=Regexp(r'^[0-9*#]+$'))


application_call_request_schema = ApplicationCallRequestSchema()
application_call_user_request_schema = ApplicationCallUserRequestSchema()
application_call_schema = ApplicationCallSchema()
application_dtmf_schema = ApplicationDTMFSchema()
application_node_schema = ApplicationNodeSchema()
application_playback_schema = ApplicationCallPlaySchema()
application_schema = ApplicationSchema()
application_snoop_schema = ApplicationSnoopSchema()
application_snoop_put_schema = ApplicationSnoopPutSchema()
