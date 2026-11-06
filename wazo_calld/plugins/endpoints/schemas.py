# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow.validate import OneOf, Range
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


class EndpointListParamsSchema(Schema):
    limit = fields.Integer(validate=Range(min=1))
    offset = fields.Integer(validate=Range(min=0), load_default=0)
    order = fields.String(
        validate=OneOf(
            ['id', 'name', 'technology', 'registered', 'current_call_count']
        ),
        load_default='name',
    )
    direction = fields.String(validate=OneOf(['asc', 'desc']), load_default='asc')


endpoint_list_params_schema = EndpointListParamsSchema()
trunk_endpoint_schema = TrunkEndpointSchema()
line_endpoint_schema = LineEndpointSchema()
