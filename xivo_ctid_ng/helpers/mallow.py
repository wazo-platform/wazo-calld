# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from marshmallow import fields


class StrictDict(fields.Dict):

    def __init__(self, key_field, value_field, *args, **kwargs):
        super(StrictDict, self).__init__(*args, **kwargs)
        self.key_field = key_field
        self.value_field = value_field

    def _deserialize(self, value, attr, data):
        value = super(StrictDict, self)._deserialize(value, attr, data)

        result = {}
        for key, inner_value in value.iteritems():
            new_key = self.key_field.deserialize(key, attr, data)
            new_value = self.value_field.deserialize(inner_value, attr, data)
            result[new_key] = new_value
        return result
