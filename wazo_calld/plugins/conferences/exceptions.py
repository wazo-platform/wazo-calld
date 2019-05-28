# Copyright 2018-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

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


class ConferenceHasNoParticipants(APIException):
    def __init__(self, tenant_uuid, conference_id):
        super().__init__(
            status_code=400,
            message='Conference "{}" has no participants'.format(conference_id),
            error_id='conference-has-no-participants',
            resource='conference',
            details={
                'conference_id': conference_id,
                'tenant_uuid': tenant_uuid,
            }
        )


class ConferenceAlreadyRecorded(APIException):
    def __init__(self, tenant_uuid, conference_id):
        super().__init__(
            status_code=400,
            message='Conference "{}" is already being recorded'.format(conference_id),
            error_id='conference-already-recorded',
            resource='conference',
            details={
                'conference_id': conference_id,
                'tenant_uuid': tenant_uuid,
            }
        )


class ConferenceNotRecorded(APIException):
    def __init__(self, tenant_uuid, conference_id):
        super().__init__(
            status_code=400,
            message='Conference "{}" is not being recorded'.format(conference_id),
            error_id='conference-not-recorded',
            resource='conference',
            details={
                'conference_id': conference_id,
                'tenant_uuid': tenant_uuid,
            }
        )


class ConferenceError(APIException):
    def __init__(self, tenant_uuid, conference_id, message):
        super().__init__(
            status_code=500,
            message='Error while operating on conference "{}": "{}"'.format(conference_id, message),
            error_id='conference-error',
            resource='conference',
            details={
                'conference_id': conference_id,
                'tenant_uuid': tenant_uuid,
                'original_message': message,
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


class UserNotParticipant(APIException):
    def __init__(self, tenant_uuid, user_uuid, conference_id):
        super().__init__(
            status_code=403,
            message='User "{}" is not a participant of the conference "{}"'.format(user_uuid, conference_id),
            error_id='user-not-participant',
            resource='conference-participant',
            details={
                'conference_id': conference_id,
                'tenant_uuid': tenant_uuid,
                'user_uuid': user_uuid,
            }
        )
