# -*- coding: UTF-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.core.auth import required_acl
from xivo_ctid_ng.core.rest_api import AuthResource


class StatusResource(AuthResource):

    def __init__(self, status_service):
        self.status_service = status_service

    @required_acl('ctid-ng.status.read')
    def get(self):
        return {
            'connections': {
                'ari': self.status_service.ari_status(),
                'bus_consumer': self.status_service.bus_consumer_status()
            }
        }, 200
