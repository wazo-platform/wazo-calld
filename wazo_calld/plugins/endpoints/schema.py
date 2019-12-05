# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo.mallow_helpers import Schema, fields


class EndpointBaseSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    type = fields.String()
    technology = fields.String(default='unknown')
    registered = fields.Boolean(default=None)
    current_call_count = fields.Integer(default=None)


class TrunkEndpointSchema(EndpointBaseSchema):
    pass


trunk_endpoint_schema = TrunkEndpointSchema()
