# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import validate
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


class EndpointListSchema(Schema):
    # passed to wazo-confd as given: order and search are wazo-confd's columns
    limit = fields.Integer(validate=validate.Range(min=1))
    offset = fields.Integer(validate=validate.Range(min=0))
    order = fields.String()
    direction = fields.String(validate=validate.OneOf(['asc', 'desc']))
    search = fields.String()


endpoint_list_schema = EndpointListSchema()
trunk_endpoint_schema = TrunkEndpointSchema()
line_endpoint_schema = LineEndpointSchema()
