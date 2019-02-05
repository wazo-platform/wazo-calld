# -*- coding: UTF-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo_ctid_ng.auth import required_acl
from xivo_ctid_ng.rest_api import AuthResource


class StatusResource(AuthResource):

    def __init__(self, status_aggregator):
        self.status_aggregator = status_aggregator

    @required_acl('ctid-ng.status.read')
    def get(self):
        return self.status_aggregator.status(), 200
