# -*- coding: UTF-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from xivo_ctid_ng.core.auth import required_acl
from xivo_ctid_ng.core.rest_api import AuthResource


class StatusResource(AuthResource):

    def __init__(self, status_aggregator):
        self.status_aggregator = status_aggregator

    @required_acl('ctid-ng.status.read')
    def get(self):
        return self.status_aggregator.status(), 200
