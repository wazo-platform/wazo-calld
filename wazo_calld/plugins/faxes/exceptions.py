# Copyright 2019-2023 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo.rest_api_helpers import APIException


class FaxFailure(APIException):
    def __init__(self, message):
        super().__init__(
            status_code=400,
            message=message,
            error_id='fax-failure',
        )
