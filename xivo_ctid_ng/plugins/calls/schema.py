# -*- coding: utf-8 -*-
# Copyright (C) 2016 Proformatique Inc.
# SPDX-License-Identifier: GPL-3.0+

from marshmallow import Schema, fields
from marshmallow.validate import Length

from xivo_ctid_ng.helpers.mallow import StrictDict


class CallRequestSourceSchema(Schema):
    user = fields.String(required=True)


class CallRequestDestinationSchema(Schema):
    context = fields.String(validate=Length(min=1), required=True)
    extension = fields.String(validate=Length(min=1), required=True)
    priority = fields.String(validate=Length(min=1), required=True)


class CallRequestSchema(Schema):
    source = fields.Nested('CallRequestSourceSchema', required=True)
    destination = fields.Nested('CallRequestDestinationSchema', required=True)
    variables = StrictDict(key_field=fields.String(required=True, validate=Length(min=1)),
                           value_field=fields.String(required=True, validate=Length(min=1)),
                           missing=dict)


class UserCallRequestSchema(Schema):
    extension = fields.String(validate=Length(min=1), required=True)
    variables = StrictDict(key_field=fields.String(required=True, validate=Length(min=1)),
                           value_field=fields.String(required=True, validate=Length(min=1)),
                           missing=dict)
