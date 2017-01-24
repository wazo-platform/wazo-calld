# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from marshmallow import Schema, fields

from xivo_ctid_ng.core.auth import get_token_user_uuid_from_request
from xivo_ctid_ng.core.auth import required_acl
from xivo_ctid_ng.core.rest_api import AuthResource


class QueuedCallSchema(Schema):
    id = fields.String(attribute='id')
    caller_id_name = fields.String()
    caller_id_number = fields.String()

queued_call_schema = QueuedCallSchema()


class SwitchboardCallsQueuedResource(AuthResource):

    def __init__(self, switchboards_service):
        self._service = switchboards_service

    @required_acl('ctid-ng.switchboards.{switchboard_uuid}.calls.queued.read')
    def get(self, switchboard_uuid):
        calls = self._service.queued_calls(switchboard_uuid)

        return {'items': queued_call_schema.dump(calls, many=True).data}


class SwitchboardCallsQueuedAnswerResource(AuthResource):

    def __init__(self, auth_client, switchboards_service):
        self._auth_client = auth_client
        self._service = switchboards_service

    @required_acl('ctid-ng.switchboards.{switchboard_uuid}.calls.queued.{call_id}.answer.update')
    def put(self, switchboard_uuid, call_id):
        user_uuid = get_token_user_uuid_from_request(self._auth_client)

        self._service.answer_queued_call(switchboard_uuid, call_id, user_uuid)

        return '', 204
