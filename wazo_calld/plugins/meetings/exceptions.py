# Copyright 2021-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo.rest_api_helpers import APIException


class MeetingParticipantError(APIException):
    def __init__(self, tenant_uuid, meeting_uuid, participant_id, message):
        super().__init__(
            status_code=500,
            message='Error while operating on participants of meeting "{}": "{}"'.format(
                meeting_uuid, message
            ),
            error_id='meeting-participant-error',
            resource='meeting-participant',
            details={
                'meeting_uuid': meeting_uuid,
                'tenant_uuid': tenant_uuid,
                'original_message': message,
                'participant_id': participant_id,
            },
        )


class NoSuchMeeting(APIException):
    def __init__(self, tenant_uuid, meeting_id):
        super().__init__(
            status_code=404,
            message=f'No such meeting: id "{meeting_id}"',
            error_id='no-such-meeting',
            resource='meeting',
            details={
                'meeting_id': meeting_id,
                'tenant_uuid': tenant_uuid,
            },
        )


class NoSuchMeetingParticipant(APIException):
    def __init__(self, tenant_uuid, meeting_id, participant_id):
        super().__init__(
            status_code=404,
            message='No such participant in meeting {}: participant id "{}"'.format(
                meeting_id, participant_id
            ),
            error_id='no-such-participant',
            resource='meeting-participant',
            details={
                'tenant_uuid': tenant_uuid,
                'meeting_id': meeting_id,
                'participant_id': participant_id,
            },
        )


class UserNotParticipant(APIException):
    def __init__(self, tenant_uuid, user_uuid, meeting_uuid):
        super().__init__(
            status_code=403,
            message='User "{}" is not a participant of the meeting "{}"'.format(
                user_uuid, meeting_uuid
            ),
            error_id='user-not-participant',
            resource='meeting-participant',
            details={
                'meeting_uuid': meeting_uuid,
                'tenant_uuid': tenant_uuid,
                'user_uuid': user_uuid,
            },
        )
