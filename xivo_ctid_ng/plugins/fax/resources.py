# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from flask import request
from xivo.tenant_flask_helpers import Tenant

from xivo_ctid_ng.auth import required_acl
from xivo_ctid_ng.rest_api import AuthResource


class FaxesResource(AuthResource):

    def __init__(self, faxes_service):
        self._service = faxes_service

    @required_acl('ctid-ng.fax.create')
    def post(self):
        tenant = Tenant.autodetect()
        self._service.send_fax(tenant.uuid, content=request.data, fax_infos=request.args)
        return '', 204
