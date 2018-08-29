# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from marshmallow import Schema, fields
from xivo_ctid_ng.helpers.mallow import StrictDict


class BaseSchema(Schema):
    class Meta:
        strict = True


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


class ApplicationSchema(Schema):
    destination_node_uuid = fields.String()


application_call_schema = ApplicationCallSchema()
application_schema = ApplicationSchema()
