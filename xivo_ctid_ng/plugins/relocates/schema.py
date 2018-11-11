# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from marshmallow import (
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
    line_id = fields.Integer(validate=Range(min=1), required=True)


class LocationField(fields.Field):

    locations = {
        'line': fields.Nested(LineLocationSchema),
        'mobile': None,
    }

    def _deserialize(self, value, attr, data):
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
    initiator_call = fields.Str(validate=Length(min=1), required=True)
    destination = fields.Str(validate=OneOf(LocationField.locations))
    location = LocationField(missing=dict)
    completions = fields.List(fields.Str(validate=OneOf(VALID_COMPLETIONS)), missing=['answer'])
    timeout = fields.Integer(validate=Range(min=1), missing=30)


user_relocate_request_schema = UserRelocateRequestSchema(strict=True)


class RelocateSchema(Schema):
    uuid = fields.Str(validate=Length(equal=36), required=True)
    relocated_call = fields.Str(validate=Length(min=1), required=True, attribute='relocated_channel')
    initiator_call = fields.Str(validate=Length(min=1), required=True, attribute='initiator_channel')
    recipient_call = fields.Str(validate=Length(min=1), required=True, attribute='recipient_channel')
    completions = fields.List(fields.Str(validate=OneOf(VALID_COMPLETIONS)), missing=['answer'])
    initiator = fields.Str(validate=Length(equal=36), required=True)
    timeout = fields.Integer(validate=Range(min=1), missing=30)

    class Meta:
        strict = True


relocate_schema = RelocateSchema()
