# Copyright 2019-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import Schema, fields, post_dump
from xivo.mallow.validate import OneOf, Range

VALID_GREETINGS = ["unavailable", "busy", "name"]
VALID_VOICEMAIL_TYPES = ["all", "personal", "global"]
VALID_VOICEMAIL_ORDER = ["id", "caller_id_name", "duration", "timestamp"]
VALID_ACCESSTYPES = ["personal", "global"]


class VoicemailMessageBaseSchema(Schema):
    id = fields.String()
    caller_id_name = fields.String()
    caller_id_num = fields.String()
    duration = fields.Integer()
    timestamp = fields.Integer()


class VoicemailFolderBaseSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    type = fields.String()


class VoicemailMessageSchema(VoicemailMessageBaseSchema):
    folder = fields.Nested(VoicemailFolderBaseSchema)


class VoicemailFolderSchema(VoicemailFolderBaseSchema):
    messages = fields.Nested(VoicemailMessageBaseSchema, many=True)


class VoicemailSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    number = fields.String()
    folders = fields.Nested(VoicemailFolderSchema, many=True)
    accesstype = fields.String(validate=OneOf(VALID_ACCESSTYPES))


class VoicemailMessageUpdateSchema(Schema):
    folder_id = fields.Integer(required=True)


class VoicemailGreetingCopySchema(Schema):
    dest_greeting = fields.String(validate=OneOf(VALID_GREETINGS))


class UnifiedVoicemailMessageSchema(VoicemailMessageBaseSchema):
    voicemail = fields.Nested(VoicemailSchema, only=("id", "name"))
    folder = fields.Nested(VoicemailFolderBaseSchema)

    @post_dump(pass_original=True)
    def compute_voicemail_type(self, data, original_data, **kwargs):
        try:
            accesstype = original_data['voicemail'].get('accesstype', 'personal')
        except KeyError:
            accesstype = 'personal'

        data['voicemail']['type'] = 'global' if accesstype == 'global' else 'personal'
        return data


class VoicemailMessagesSchema(Schema):
    items = fields.Nested(UnifiedVoicemailMessageSchema, many=True)
    total = fields.Integer()


class VoicemailMessagesGetSchema(Schema):
    limit = fields.Integer(validate=Range(1))
    offset = fields.Integer(validate=Range(0))
    direction = fields.String(validate=OneOf(("asc", "desc")), load_default="asc")
    order = fields.String(
        validate=OneOf(VALID_VOICEMAIL_ORDER), load_default="timestamp"
    )
    voicemail_type = fields.String(
        validate=OneOf(VALID_VOICEMAIL_TYPES), load_default="all"
    )


voicemail_schema = VoicemailSchema()
voicemail_folder_schema = VoicemailFolderSchema()
voicemail_message_schema = VoicemailMessageSchema()
voicemail_message_update_schema = VoicemailMessageUpdateSchema()
voicemail_greeting_copy_schema = VoicemailGreetingCopySchema()
voicemail_messages_schema = VoicemailMessagesSchema()
voicemail_messages_get_schema = VoicemailMessagesGetSchema()
