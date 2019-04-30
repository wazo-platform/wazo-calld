# Copyright 2015-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_calld.exceptions import APIException


class TooManyChannels(Exception):
    def __init__(self, channels):
        self.channels = channels


class NotEnoughChannels(Exception):
    pass


class UserMissingMainLine(APIException):

    def __init__(self, user_uuid):
        super().__init__(
            status_code=400,
            message='User has no main line',
            error_id='user-missing-main-line',
            details={
                'user_uuid': user_uuid
            }
        )


class InvalidUserUUID(APIException):

    def __init__(self, user_uuid):
        super().__init__(
            status_code=400,
            message='Invalid user: not found',
            error_id='invalid-user',
            details={
                'user_uuid': user_uuid
            }
        )


class InvalidUserLine(APIException):

    def __init__(self, user_id, line_id):
        super().__init__(
            status_code=400,
            message='User has no such line',
            error_id='invalid-user-line',
            details={
                'user_id': user_id,
                'line_id': line_id,
            }
        )


class NoSuchUserVoicemail(APIException):

    def __init__(self, user_uuid):
        super().__init__(
            status_code=404,
            message='No such user voicemail',
            error_id='no-such-user-voicemail',
            details={
                'user_uuid': user_uuid,
            }
        )


class NoSuchVoicemail(APIException):

    def __init__(self, voicemail_id):
        super().__init__(
            status_code=404,
            message='No such voicemail',
            error_id='no-such-voicemail',
            details={
                'voicemail_id': voicemail_id,
            }
        )
