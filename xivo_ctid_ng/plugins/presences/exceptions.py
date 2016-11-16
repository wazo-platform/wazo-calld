# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# Copyright (C) 2016 Proformatique, Inc.
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.core.exceptions import APIException


class InvalidCredentials(APIException):

    def __init__(self, xivo_uuid):
        super(InvalidCredentials, self).__init__(
            status_code=502,
            message='invalid credentials cannot authenticate',
            error_id='invalid-credentials',
            details={
                'xivo_uuid': xivo_uuid,
            },
        )


class MissingCredentials(APIException):

    def __init__(self, xivo_uuid):
        super(MissingCredentials, self).__init__(
            status_code=400,
            message='missing credentials cannot authenticate',
            error_id='missing-credentials',
            details={
                'xivo_uuid': xivo_uuid,
            },
        )


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

    def __init__(self, xivo_uuid, user_uuid):
        super(NoSuchUser, self).__init__(
            status_code=404,
            message='no such user',
            error_id='no-such-user',
            details={
                'xivo_uuid': xivo_uuid,
                'user_uuid': user_uuid,
            },
        )


class XiVOAuthUnreachable(APIException):

    def __init__(self, xivo_uuid, error):
        super(XiVOAuthUnreachable, self).__init__(
            status_code=503,
            message='xivo-auth server unreachable',
            error_id='xivo-auth-unreachable',
            details={
                'xivo_uuid': xivo_uuid,
                'original_error': str(error),
                'service': 'xivo-auth',
            }
        )


class XiVOCtidNgUnreachable(APIException):

    def __init__(self, xivo_uuid, error):
        super(XiVOCtidNgUnreachable, self).__init__(
            status_code=503,
            message='xivo-ctid-ng server unreachable',
            error_id='xivo-ctid-ng-unreachable',
            details={
                'xivo_uuid': xivo_uuid,
                'original_error': str(error),
                'service': 'xivo-ctid-ng',
            }
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
                'service': 'xivo-ctid',
            }
        )
