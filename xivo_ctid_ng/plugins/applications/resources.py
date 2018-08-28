# -*- coding: utf-8 -*-
# Copyright 2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.auth import required_acl
from xivo_ctid_ng.rest_api import AuthResource

from .schema import (
    application_schema,
)


class ApplicationItem(AuthResource):

    def __init__(self, service):
        self._service = service

    @required_acl('ctid-ng.applications.{application_uuid}.read')
    def get(self, application_uuid):
        application = self._service.get_application(application_uuid)
        return application_schema.dump(application).data
