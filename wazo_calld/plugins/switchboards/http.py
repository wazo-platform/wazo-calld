# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from flask import request
from xivo.tenant_flask_helpers import Tenant, token

from wazo_calld.auth import required_acl
from wazo_calld.http import AuthResource

from .schemas import answer_call_schema, held_call_schema, queued_call_schema


class SwitchboardCallsQueuedResource(AuthResource):
    def __init__(self, switchboards_service):
        self._service = switchboards_service

    @required_acl('calld.switchboards.{switchboard_uuid}.calls.queued.read')
    def get(self, switchboard_uuid):
        tenant = Tenant.autodetect()
        calls = self._service.queued_calls(tenant.uuid, switchboard_uuid)

        return {'items': queued_call_schema.dump(calls, many=True)}


class SwitchboardCallQueuedAnswerResource(AuthResource):
    def __init__(self, switchboards_service):
        self._service = switchboards_service

    @required_acl(
        'calld.switchboards.{switchboard_uuid}.calls.queued.{call_id}.answer.update'
    )
    def put(self, switchboard_uuid, call_id):
        tenant = Tenant.autodetect()
        user_uuid = token.user_uuid

        line_id = answer_call_schema.load(request.args).get('line_id')

        call_id = self._service.answer_queued_call(
            tenant.uuid, switchboard_uuid, call_id, user_uuid, line_id
        )

        return {'call_id': call_id}, 200


class SwitchboardCallHeldResource(AuthResource):
    def __init__(self, switchboards_service):
        self._service = switchboards_service

    @required_acl('calld.switchboards.{switchboard_uuid}.calls.held.{call_id}.update')
    def put(self, switchboard_uuid, call_id):
        tenant = Tenant.autodetect()
        self._service.hold_call(tenant.uuid, switchboard_uuid, call_id)
        return '', 204


class SwitchboardCallsHeldResource(AuthResource):
    def __init__(self, switchboards_service):
        self._service = switchboards_service

    @required_acl('calld.switchboards.{switchboard_uuid}.calls.held.read')
    def get(self, switchboard_uuid):
        tenant = Tenant.autodetect()
        calls = self._service.held_calls(tenant.uuid, switchboard_uuid)

        return {'items': held_call_schema.dump(calls, many=True)}


class SwitchboardCallHeldAnswerResource(AuthResource):
    def __init__(self, switchboards_service):
        self._service = switchboards_service

    @required_acl(
        'calld.switchboards.{switchboard_uuid}.calls.held.{call_id}.answer.update'
    )
    def put(self, switchboard_uuid, call_id):
        tenant = Tenant.autodetect()
        user_uuid = token.user_uuid

        line_id = answer_call_schema.load(request.args).get('line_id')

        call_id = self._service.answer_held_call(
            tenant.uuid, switchboard_uuid, call_id, user_uuid, line_id
        )

        return {'call_id': call_id}, 200
