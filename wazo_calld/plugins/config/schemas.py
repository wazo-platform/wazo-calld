# Copyright 2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import Schema
from marshmallow.validate import Equal

from xivo.mallow import fields


class ConfigPatchSchema(Schema):
    op = fields.String(validate=Equal('replace'))
    path = fields.String(validate=Equal('/debug'))
    value = fields.Boolean()


config_patch_schema = ConfigPatchSchema()
