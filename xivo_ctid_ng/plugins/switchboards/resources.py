# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from marshmallow import Schema, fields

from xivo_ctid_ng.core.auth import required_acl
from xivo_ctid_ng.core.rest_api import AuthResource


class QueuedCallSchema(Schema):
    id = fields.String(attribute='id')
    caller_id_name = fields.String()
    caller_id_number = fields.String()

schema = QueuedCallSchema()


class SwitchboardCallsQueuedResource(AuthResource):

    def __init__(self, switchboards_service):
        self._service = switchboards_service

    @required_acl('ctid-ng.switchboards.{switchboard_uuid}.calls.queued.read')
    def get(self, switchboard_uuid):
        calls = self._service.queued_calls(switchboard_uuid)

        return {'items': schema.dump(calls, many=True).data}
