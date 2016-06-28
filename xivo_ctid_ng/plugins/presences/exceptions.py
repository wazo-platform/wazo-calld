# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.core.exceptions import APIException


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
