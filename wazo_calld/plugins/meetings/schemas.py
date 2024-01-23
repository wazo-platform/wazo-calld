# Copyright 2021-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import EXCLUDE, Schema
from xivo.mallow import fields


class ParticipantSchema(Schema):
    class Meta:
        ordered = True
        unknown = EXCLUDE

    id = fields.String()
    caller_id_name = fields.String()
    caller_id_number = fields.String()
    call_id = fields.String()
    user_uuid = fields.String(allow_none=True)


class StatusSchema(Schema):
    class Meta:
        ordered = True
        unknown = EXCLUDE

    full = fields.Boolean()


participant_schema = ParticipantSchema()
status_schema = StatusSchema()
