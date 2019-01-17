# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo.rest_api_helpers import APIException


class NoSuchConference(APIException):
    def __init__(self, tenant_uuid, conference_id):
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


class NoSuchParticipant(APIException):
    def __init__(self, tenant_uuid, conference_id, participant_id):
        super().__init__(
            status_code=404,
            message='Conference id "{}" has no such participant: id "{}"'.format(conference_id, participant_id),
            error_id='no-such-participant',
            resource='conference-participant',
            details={
                'tenant_uuid': tenant_uuid,
                'conference_id': conference_id,
                'participant_id': participant_id,
            }
        )


class ConferenceParticipantError(APIException):
    def __init__(self, tenant_uuid, conference_id, participant_id, message):
        super().__init__(
            status_code=500,
            message='Error while operating on participants of conference "{}": "{}"'.format(conference_id, message),
            error_id='conference-participant-error',
            resource='conference-participant',
            details={
                'conference_id': conference_id,
                'tenant_uuid': tenant_uuid,
                'original_message': message,
                'participant_id': participant_id,
            }
        )
