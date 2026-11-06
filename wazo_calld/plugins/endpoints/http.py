# Copyright 2019-2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from flask import request
from xivo.tenant_flask_helpers import Tenant

from wazo_calld.auth import required_acl
from wazo_calld.http import AuthResource

from .schemas import (
    endpoint_list_params_schema,
    line_endpoint_schema,
    trunk_endpoint_schema,
)


class LineEndpoints(AuthResource):
    def __init__(self, endpoints_service):
        self._endpoints_service = endpoints_service

    @required_acl('calld.lines.read')
    def get(self):
        tenant_uuid = Tenant.autodetect().uuid

        params = endpoint_list_params_schema.load(request.args.to_dict())
        items, total, filtered = self._endpoints_service.list_lines(
            tenant_uuid, **params
        )
        result = {
            'items': line_endpoint_schema.dump(items, many=True),
            'total': total,
            'filtered': filtered,
        }

        return result, 200


class TrunkEndpoints(AuthResource):
    def __init__(self, endpoints_service):
        self._endpoints_service = endpoints_service

    @required_acl('calld.trunks.read')
    def get(self):
        tenant_uuid = Tenant.autodetect().uuid

        params = endpoint_list_params_schema.load(request.args.to_dict())
        items, total, filtered = self._endpoints_service.list_trunks(
            tenant_uuid, **params
        )
        result = {
            'items': trunk_endpoint_schema.dump(items, many=True),
            'total': total,
            'filtered': filtered,
        }

        return result, 200
