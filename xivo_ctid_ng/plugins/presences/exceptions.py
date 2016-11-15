# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# Copyright (C) 2016 Proformatique, Inc.
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.core.exceptions import APIException


class NoSuchLine(APIException):

    def __init__(self, line_id):
        super(NoSuchLine, self).__init__(
            status_code=404,
            message='no such line',
            error_id='no-such-line',
            details={
                'line_id': line_id,
            },
        )


class NoSuchUser(APIException):

    def __init__(self, user_uuid):
        super(NoSuchUser, self).__init__(
            status_code=404,
            message='no such user',
            error_id='no-such-user',
            details={
                'user_uuid': user_uuid,
            },
        )


class XiVOCtidUnreachable(APIException):

    def __init__(self, xivo_ctid_config, error):
        super(XiVOCtidUnreachable, self).__init__(
            status_code=503,
            message='xivo-ctid server unreachable',
            error_id='xivo-ctid-unreachable',
            details={
                'xivo_ctid_config': xivo_ctid_config,
                'original_error': str(error),
            }
        )
