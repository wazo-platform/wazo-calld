# -*- coding: utf-8 -*-
# Copyright 2015-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import logging

from flask import request

from xivo_ctid_ng.auth import required_acl
from xivo_ctid_ng.auth import get_token_user_uuid_from_request
from xivo_ctid_ng.rest_api import AuthResource

from .schema import call_schema
from .schema import CallRequestSchema
from .schema import UserCallRequestSchema

logger = logging.getLogger(__name__)


call_request_schema = CallRequestSchema(strict=True)
user_call_request_schema = UserCallRequestSchema(strict=True)


class CallsResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('ctid-ng.calls.read')
    def get(self):
        application_filter = request.args.get('application')
        application_instance_filter = request.args.get('application_instance')

        calls = self.calls_service.list_calls(application_filter, application_instance_filter)

        return {
            'items': call_schema.dump(calls, many=True).data,
        }, 200

    @required_acl('ctid-ng.calls.create')
    def post(self):
        request_body = call_request_schema.load(request.get_json(force=True)).data

        call = self.calls_service.originate(request_body)

        return call_schema.dump(call).data, 201


class MyCallsResource(AuthResource):

    def __init__(self, auth_client, calls_service):
        self.auth_client = auth_client
        self.calls_service = calls_service

    @required_acl('ctid-ng.users.me.calls.read')
    def get(self):
        application_filter = request.args.get('application')
        application_instance_filter = request.args.get('application_instance')
        user_uuid = get_token_user_uuid_from_request(self.auth_client)

        calls = self.calls_service.list_calls_user(user_uuid, application_filter, application_instance_filter)

        return {
            'items': call_schema.dump(calls, many=True).data,
        }, 200

    @required_acl('ctid-ng.users.me.calls.create')
    def post(self):
        request_body = user_call_request_schema.load(request.get_json(force=True)).data

        user_uuid = get_token_user_uuid_from_request(self.auth_client)

        call = self.calls_service.originate_user(request_body, user_uuid)

        return call_schema.dump(call).data, 201


class CallResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('ctid-ng.calls.{call_id}.read')
    def get(self, call_id):
        call = self.calls_service.get(call_id)

        return call_schema.dump(call).data

    @required_acl('ctid-ng.calls.{call_id}.delete')
    def delete(self, call_id):
        self.calls_service.hangup(call_id)

        return None, 204


class MyCallResource(AuthResource):

    def __init__(self, auth_client, calls_service):
        self.auth_client = auth_client
        self.calls_service = calls_service

    @required_acl('ctid-ng.users.me.calls.{call_id}.delete')
    def delete(self, call_id):
        user_uuid = get_token_user_uuid_from_request(self.auth_client)
        self.calls_service.hangup_user(call_id, user_uuid)

        return None, 204


class ConnectCallToUserResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('ctid-ng.calls.{call_id}.user.{user_uuid}.update')
    def put(self, call_id, user_uuid):
        new_call_id = self.calls_service.connect_user(call_id, user_uuid)
        new_call = self.calls_service.get(new_call_id)

        return call_schema.dump(new_call).data
