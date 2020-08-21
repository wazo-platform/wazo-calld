# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_calld.exceptions import APIException


class AdhocConferenceException(APIException):
    pass


class HostCallNotFound(AdhocConferenceException):
    def __init__(self, host_call_id):
        super().__init__(
            status_code=400,
            message='Adhoc conference creation error: host call not found',
            error_id='host-call-not-found',
            details={
                'host_call_id': host_call_id,
            }
        )


class ParticipantCallNotFound(AdhocConferenceException):
    def __init__(self, participant_call_id):
        super().__init__(
            status_code=400,
            message='Adhoc conference creation error: participant call not found',
            error_id='participant-call-not-found',
            details={
                'participant_call_id': participant_call_id,
            }
        )


class HostPermissionDenied(AdhocConferenceException):
    def __init__(self, host_call_id, user_uuid):
        super().__init__(
            status_code=400,
            message='Adhoc conference creation error: user does not own host call',
            error_id='host-call-permission-denied',
            details={
                'host_call_id': host_call_id,
                'user_uuid': user_uuid,
            }
        )


class AdhocConferenceCreationError(AdhocConferenceException):
    def __init__(self, message, details=None):
        details = details or {}
        super().__init__(
            status_code=400,
            message=message,
            error_id='host-call-creation-error',
            details=details
        )
