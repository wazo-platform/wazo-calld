# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo.mallow import fields
from xivo.mallow_helpers import Schema


class FaxCreationRequestSchema(Schema):
    context = fields.String(required=True)
    extension = fields.String(required=True)
    caller_id = fields.String(missing='Wazo Fax')


class UserFaxCreationRequestSchema(Schema):
    extension = fields.String(required=True)
    caller_id = fields.String(missing='Wazo Fax')


fax_creation_request_schema = FaxCreationRequestSchema()
user_fax_creation_request_schema = UserFaxCreationRequestSchema()
