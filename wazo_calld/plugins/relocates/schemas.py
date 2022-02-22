# Copyright 2017-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from marshmallow import (
    EXCLUDE,
    fields,
    Schema,
    ValidationError,
)
from marshmallow.validate import OneOf, Length, Range

VALID_COMPLETIONS = [
    'answer',
    'api',
]


class LineLocationSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    line_id = fields.Integer(validate=Range(min=1), required=True)
    contact = fields.String()


class LocationField(fields.Field):
    class Meta:
        unknown = EXCLUDE

    locations = {
        'line': fields.Nested(LineLocationSchema, unknown=EXCLUDE),
        'mobile': None,
    }

    def _deserialize(self, value, attr, data, **kwargs):
        destination = data.get('destination')
        try:
            concrete_location = self.locations.get(destination)
        except TypeError:
            raise ValidationError({
                'message': 'Invalid destination',
                'constraint_id': 'destination-type',
                'constraint': {
                    'type': 'string',
                }
            })

        if not concrete_location:
            return {}
        return concrete_location._deserialize(value, attr, data)


class UserRelocateRequestSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    initiator_call = fields.Str(validate=Length(min=1), required=True)
    destination = fields.Str(validate=OneOf(LocationField.locations))
    location = LocationField(missing=dict)
    completions = fields.List(fields.Str(validate=OneOf(VALID_COMPLETIONS)), missing=['answer'])
    timeout = fields.Integer(validate=Range(min=1), missing=30)
    auto_answer = fields.Boolean(missing=False)


user_relocate_request_schema = UserRelocateRequestSchema()


class RelocateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    uuid = fields.Str(validate=Length(equal=36), required=True)
    relocated_call = fields.Str(validate=Length(min=1), required=True, attribute='relocated_channel')
    initiator_call = fields.Str(validate=Length(min=1), required=True, attribute='initiator_channel')
    recipient_call = fields.Str(validate=Length(min=1), required=True, attribute='recipient_channel')
    completions = fields.List(fields.Str(validate=OneOf(VALID_COMPLETIONS)), missing=['answer'])
    initiator = fields.Str(validate=Length(equal=36), required=True)
    timeout = fields.Integer(validate=Range(min=1), missing=30)
    auto_answer = fields.Boolean(missing=False)


relocate_schema = RelocateSchema()
