# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from marshmallow import Schema, fields


class BaseSchema(Schema):
    class Meta:
        strict = True


class ApplicationSchema(Schema):
    destination_node_uuid = fields.String()


application_schema = ApplicationSchema()
