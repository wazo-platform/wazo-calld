# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_calld.exceptions import APIException


class InvalidListParameters(APIException):
    def __init__(self, confd_errors):
        super().__init__(
            status_code=400,
            message=' '.join(str(error) for error in confd_errors),
            error_id='invalid-list-parameters',
            details={'wazo_confd_errors': confd_errors},
        )
