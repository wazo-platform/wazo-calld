# -*- coding: utf-8 -*-
# Copyright 2016 Proformatique Inc.
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.core.exceptions import APIException


class InvalidVoicemailID(APIException):

    def __init__(self, voicemail_id):
        super(InvalidVoicemailID, self).__init__(
            status_code=400,
            message='Invalid voicemail ID',
            error_id='invalid-voicemail-id',
            details={
                'voicemail_id': voicemail_id,
            }
        )


class InvalidVoicemailFolderID(APIException):

    def __init__(self, folder_id):
        super(InvalidVoicemailFolderID, self).__init__(
            status_code=400,
            message='Invalid voicemail folder ID',
            error_id='invalid-voicemail-folder-id',
            details={
                'folder_id': folder_id,
            }
        )


class InvalidVoicemailMessageID(APIException):

    def __init__(self, message_id):
        super(InvalidVoicemailMessageID, self).__init__(
            status_code=400,
            message='Invalid voicemail message ID',
            error_id='invalid-voicemail-message-id',
            details={
                'message_id': message_id,
            }
        )


class NoSuchVoicemailFolder(APIException):

    def __init__(self, **kwargs):
        super(NoSuchVoicemailFolder, self).__init__(
            status_code=404,
            message='No such voicemail folder',
            error_id='no-such-voicemail-folder',
            details=kwargs,
        )


class NoSuchVoicemailMessage(APIException):

    def __init__(self, message_id):
        super(NoSuchVoicemailMessage, self).__init__(
            status_code=404,
            message='No such voicemail message',
            error_id='no-such-voicemail-message',
            details={
                'message_id': message_id,
            }
        )


class VoicemailMessageStorageError(APIException):

    def __init__(self):
        super(VoicemailMessageStorageError, self).__init__(
            status_code=500,
            message='Invalid voicemail message format',
            error_id='invalid-voicemail-message-format',
        )
