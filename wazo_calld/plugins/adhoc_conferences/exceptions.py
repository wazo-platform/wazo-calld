# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_calld.exceptions import APIException


class AdhocConferenceException(APIException):
    pass


class AdhocConferenceCreationError(AdhocConferenceException):
    def __init__(self, message, details=None):
        details = details or {}
        super().__init__(
            status_code=400,
            message=message,
            error_id='host-call-creation-error',
            details=details
        )


class AdhocConferenceNotFound(AdhocConferenceException):
    def __init__(self, adhoc_conference_id):
        super().__init__(
            status_code=404,
            message='Adhoc conference not found',
            error_id='adhoc-conference-not-found',
            details={
                'adhoc_conference_id': adhoc_conference_id,
            }
        )


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


class HostCallAlreadyInConference(AdhocConferenceException):
    def __init__(self, host_call_id):
        super().__init__(
            status_code=409,
            message='Adhoc conference creation error: host already in conference',
            error_id='host-already-in-conference',
            details={
                'host_call_id': host_call_id,
            }
        )


class ParticipantCallAlreadyInConference(AdhocConferenceException):
    def __init__(self, participant_call_id):
        super().__init__(
            status_code=409,
            message='Adhoc conference error: participant already in conference',
            error_id='participant-already-in-conference',
            details={
                'participant_call_id': participant_call_id,
            }
        )


class ParticipantCallNotFound(AdhocConferenceException):
    def __init__(self, participant_call_id):
        super().__init__(
            status_code=400,
            message='Adhoc conference participant call not found',
            error_id='participant-call-not-found',
            details={
                'participant_call_id': participant_call_id,
            }
        )
