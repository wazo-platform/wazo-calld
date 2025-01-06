# Copyright 2019-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo.mallow_helpers import Schema, fields


class EndpointBaseSchema(Schema):
    id = fields.Integer()
    name = fields.String()
    type = fields.String()
    technology = fields.String(dump_default='unknown')
    registered = fields.Boolean(dump_default=None)
    current_call_count = fields.Integer(dump_default=None)


class LineEndpointSchema(EndpointBaseSchema):
    pass


class TrunkEndpointSchema(EndpointBaseSchema):
    pass


trunk_endpoint_schema = TrunkEndpointSchema()
line_endpoint_schema = LineEndpointSchema()
