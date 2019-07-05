# Copyright 2016-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_calld.exceptions import APIException


class InvalidVoicemailID(APIException):

    def __init__(self, voicemail_id):
        super().__init__(
            status_code=400,
            message='Invalid voicemail ID',
            error_id='invalid-voicemail-id',
            details={
                'voicemail_id': voicemail_id,
            }
        )


class InvalidVoicemailFolderID(APIException):

    def __init__(self, folder_id):
        super().__init__(
            status_code=400,
            message='Invalid voicemail folder ID',
            error_id='invalid-voicemail-folder-id',
            details={
                'folder_id': folder_id,
            }
        )


class InvalidVoicemailMessageID(APIException):

    def __init__(self, message_id):
        super().__init__(
            status_code=400,
            message='Invalid voicemail message ID',
            error_id='invalid-voicemail-message-id',
            details={
                'message_id': message_id,
            }
        )


class NoSuchVoicemailFolder(APIException):

    def __init__(self, **kwargs):
        super().__init__(
            status_code=404,
            message='No such voicemail folder',
            error_id='no-such-voicemail-folder',
            details=kwargs,
        )


class NoSuchVoicemailMessage(APIException):

    def __init__(self, message_id):
        super().__init__(
            status_code=404,
            message='No such voicemail message',
            error_id='no-such-voicemail-message',
            details={
                'message_id': message_id,
            }
        )


class VoicemailMessageStorageError(APIException):

    def __init__(self):
        super().__init__(
            status_code=500,
            message='Invalid voicemail message format',
            error_id='invalid-voicemail-message-format',
        )


class InvalidVoicemailGreeting(APIException):

    def __init__(self, greeting):
        super().__init__(
            status_code=404,
            message='Invalid voicemail greeting',
            error_id='invalid-voicemail-greeting',
            details={
                'greeting': greeting,
            }
        )


class NoSuchVoicemailGreeting(APIException):

    def __init__(self, greeting):
        super().__init__(
            status_code=404,
            message='No such voicemail greeting',
            error_id='no-such-voicemail-greeting',
            details={
                'greeting': greeting,
            }
        )
