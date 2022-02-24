# Copyright 2016-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import fields


class StrictDict(fields.Dict):

    def __init__(self, key_field, value_field, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.key_field = key_field
        self.value_field = value_field

    def _deserialize(self, value, attr, data, **kwargs):
        value = super()._deserialize(value, attr, data, **kwargs)

        result = {}
        for key, inner_value in value.items():
            new_key = self.key_field.deserialize(key, attr, data, **kwargs)
            new_value = self.value_field.deserialize(inner_value, attr, data, **kwargs)
            result[new_key] = new_value
        return result
