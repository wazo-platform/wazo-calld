# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo.tenant_flask_helpers import Tenant

from wazo_calld.auth import required_acl
from wazo_calld.http import AuthResource


class TrunkEndpoints(AuthResource):

    def __init__(self, endpoints_service):
        self._endpoints_service = endpoints_service

    @required_acl('calld.endpoints.trunks.read')
    def get(self):
        tenant_uuid = Tenant.autodetect().uuid

        items, total, filtered = self._endpoints_service.list_trunks(tenant_uuid)

        # TODO(pcm): add a schema to format the result
        result = {'items': items, 'total': total, 'filtered': filtered}

        return result, 200
