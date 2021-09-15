# Copyright 2019-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import (
    EXCLUDE,
    Schema,
)
from xivo.mallow import fields


class ParticipantSchema(Schema):

    class Meta:
        ordered = True
        unknown = EXCLUDE

    uuid = fields.String()
    caller_id_name = fields.String()
    caller_id_number = fields.String()
    call_id = fields.String()
    user_uuid = fields.String(allow_none=True)


participant_schema = ParticipantSchema()
