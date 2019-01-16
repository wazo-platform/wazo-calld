# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo.rest_api_helpers import APIException


class NoSuchConference(APIException):
    def __init__(self, conference_id, tenant_uuid):
        super().__init__(
            status_code=404,
            message='No such conference: id "{}"'.format(conference_id),
            error_id='no-such-conference',
            resource='conference',
            details={
                'conference_id': conference_id,
                'tenant_uuid': tenant_uuid,
            }
        )


class ParticipantListError(APIException):
    def __init__(self, conference_id, tenant_uuid, message):
        super().__init__(
            status_code=500,
            message='Error while listing participants of conference "{}": "{}"'.format(conference_id, message),
            error_id='participant-list-error',
            resource='conference',
            details={
                'conference_id': conference_id,
                'tenant_uuid': tenant_uuid,
                'original_message': message,
            }
        )
