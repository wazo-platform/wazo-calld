# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import marshmallow

from flask import request

from xivo.tenant_flask_helpers import Tenant

from wazo_calld import exceptions
from wazo_calld.auth import required_acl
from wazo_calld.http import AuthResource

from .schema import endpoint_list_schema, trunk_endpoint_schema


class TrunkEndpoints(AuthResource):

    def __init__(self, endpoints_service):
        self._endpoints_service = endpoints_service

    @required_acl('calld.trunks.read')
    def get(self):
        tenant_uuid = Tenant.autodetect().uuid
        try:
            list_params = endpoint_list_schema.load(request.args)
        except marshmallow.ValidationError as e:
            raise exceptions.InvalidListParamException(e.messages)

        items, total, filtered = self._endpoints_service.list_trunks(tenant_uuid, list_params)
        result = {
            'items': trunk_endpoint_schema.dump(items, many=True),
            'total': total,
            'filtered': filtered,
        }

        return result, 200
