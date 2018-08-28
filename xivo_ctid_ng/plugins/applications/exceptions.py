# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.exceptions import APIException


class NoSuchApplication(APIException):

    def __init__(self, application_uuid):
        super(NoSuchApplication, self).__init__(
            status_code=404,
            message='No such application',
            error_id='no-such-application',
            details={
                'application_uuid': str(application_uuid),
            }
        )
