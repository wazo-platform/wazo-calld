# Copyright 2017-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from xivo.tenant_flask_helpers import Tenant

from marshmallow import Schema, fields

from wazo_calld.auth import (
    get_token_user_uuid_from_request,
    required_acl,
)
from wazo_calld.http import AuthResource


class QueuedCallSchema(Schema):
    id = fields.String(attribute='id')
    caller_id_name = fields.String()
    caller_id_number = fields.String()


queued_call_schema = QueuedCallSchema()


class HeldCallSchema(Schema):
    id = fields.String(attribute='id')
    caller_id_name = fields.String()
    caller_id_number = fields.String()


held_call_schema = HeldCallSchema()


class SwitchboardCallsQueuedResource(AuthResource):

    def __init__(self, switchboards_service):
        self._service = switchboards_service

    @required_acl('calld.switchboards.{switchboard_uuid}.calls.queued.read')
    def get(self, switchboard_uuid):
        tenant = Tenant.autodetect()
        calls = self._service.queued_calls(tenant.uuid, switchboard_uuid)

        return {'items': queued_call_schema.dump(calls, many=True).data}


class SwitchboardCallQueuedAnswerResource(AuthResource):

    def __init__(self, auth_client, switchboards_service):
        self._auth_client = auth_client
        self._service = switchboards_service

    @required_acl('calld.switchboards.{switchboard_uuid}.calls.queued.{call_id}.answer.update')
    def put(self, switchboard_uuid, call_id):
        tenant = Tenant.autodetect()
        user_uuid = get_token_user_uuid_from_request(self._auth_client)

        call_id = self._service.answer_queued_call(
            tenant.uuid, switchboard_uuid, call_id, user_uuid
        )

        return {'call_id': call_id}, 200


class SwitchboardCallHeldResource(AuthResource):

    def __init__(self, switchboards_service):
        self._service = switchboards_service

    @required_acl('calld.switchboards.{switchboard_uuid}.calls.held.{call_id}.update')
    def put(self, switchboard_uuid, call_id):
        self._service.hold_call(switchboard_uuid, call_id)
        return '', 204


class SwitchboardCallsHeldResource(AuthResource):

    def __init__(self, switchboards_service):
        self._service = switchboards_service

    @required_acl('calld.switchboards.{switchboard_uuid}.calls.held.read')
    def get(self, switchboard_uuid):
        calls = self._service.held_calls(switchboard_uuid)

        return {'items': held_call_schema.dump(calls, many=True).data}


class SwitchboardCallHeldAnswerResource(AuthResource):

    def __init__(self, auth_client, switchboards_service):
        self._auth_client = auth_client
        self._service = switchboards_service

    @required_acl('calld.switchboards.{switchboard_uuid}.calls.held.{call_id}.answer.update')
    def put(self, switchboard_uuid, call_id):
        user_uuid = get_token_user_uuid_from_request(self._auth_client)

        call_id = self._service.answer_held_call(switchboard_uuid, call_id, user_uuid)

        return {'call_id': call_id}, 200
