# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from wazo_calld.auth import required_acl
from wazo_calld.http import AuthResource


class TrunkEndpoints(AuthResource):

    @required_acl('calld.endpoints.trunks.read')
    def get(self):
        result = {'items': [], 'total': 0, 'filtered': 0}
        return result, 200
