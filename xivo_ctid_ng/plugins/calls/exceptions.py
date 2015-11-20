# -*- coding: utf-8 -*-
# Copyright (C) 2015 Avencall
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>

from xivo_ctid_ng.core.exceptions import APIException


class NoSuchCall(APIException):

    def __init__(self, call_id):
        super(NoSuchCall, self).__init__(
            status_code=404,
            message='No such call',
            error_id='no-such-call',
            details={
                'call_id': call_id
            }
        )


class XiVOConfdUnreachable(APIException):

    def __init__(self, xivo_confd_config, error):
        super(XiVOConfdUnreachable, self).__init__(
            status_code=503,
            message='xivo-confd server unreachable',
            error_id='xivo-confd-unreachable',
            details={
                'xivo_confd_config': xivo_confd_config,
                'original_error': str(error),
            }
        )
