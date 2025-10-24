# Copyright 2019-2025 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import StrEnum, auto

from marshmallow import Schema, fields
from xivo.mallow.validate import OneOf

VALID_GREETINGS = ["unavailable", "busy", "name"]
VALID_VOICEMAIL_TYPES = ["all", "personal", "shared"]


class VoicemailTypeEnum(StrEnum):
    personal = auto()
    shared = auto()


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
    shared = fields.Boolean()


class VoicemailMessageUpdateSchema(Schema):
    folder_id = fields.Integer(required=True)


class VoicemailGreetingCopySchema(Schema):
    dest_greeting = fields.String(validate=OneOf(VALID_GREETINGS))


class UnifiedVoicemailMessageSchema(VoicemailMessageBaseSchema):
    voicemail = fields.Nested(VoicemailSchema, only=("id", "name", "shared"))
    folder = fields.Nested(VoicemailFolderBaseSchema)


class VoicemailMessagesSchema(Schema):
    items = fields.Nested(UnifiedVoicemailMessageSchema, many=True)


class VoicemailMessagesGetSchema(Schema):
    limit = fields.Integer()
    offset = fields.Integer()
    direction = fields.String(validate=OneOf("asc", "desc"), load_default="desc")
    order = fields.String(validate=OneOf("timestamp"), load_default="timestamp")
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
