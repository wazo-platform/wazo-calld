# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.core.exceptions import APIException


class TooManyChannels(Exception):
    def __init__(self, channels):
        self.channels = channels


class NotEnoughChannels(Exception):
    pass


class UserHasNoLine(APIException):

    def __init__(self, user_uuid):
        super(UserHasNoLine, self).__init__(
            status_code=400,
            message='Invalid user: user has no line',
            error_id='user-has-no-line',
            details={
                'user_uuid': user_uuid
            }
        )


class InvalidUserUUID(APIException):

    def __init__(self, user_uuid):
        super(InvalidUserUUID, self).__init__(
            status_code=400,
            message='Invalid user: not found',
            error_id='invalid-user',
            details={
                'user_uuid': user_uuid
            }
        )
