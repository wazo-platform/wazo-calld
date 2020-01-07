# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import Schema, fields

from xivo.mallow.validate import OneOf

VALID_GREETINGS = ["unavailable", "busy", "name"]


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


class VoicemailMessageUpdateSchema(Schema):
    folder_id = fields.Integer(required=True)


class VoicemailGreetingCopySchema(Schema):
    dest_greeting = fields.String(validate=OneOf(VALID_GREETINGS))


voicemail_schema = VoicemailSchema()
voicemail_folder_schema = VoicemailFolderSchema()
voicemail_message_schema = VoicemailMessageSchema()
voicemail_message_update_schema = VoicemailMessageUpdateSchema()
voicemail_greeting_copy_schema = VoicemailGreetingCopySchema()
