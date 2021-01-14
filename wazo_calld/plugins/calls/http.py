# Copyright 2015-2021 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from flask import request

from wazo_calld.auth import required_acl
from wazo_calld.auth import get_token_user_uuid_from_request
from wazo_calld.http import AuthResource

from .schemas import call_schema
from .schemas import CallDtmfSchema
from .schemas import CallRequestSchema
from .schemas import UserCallRequestSchema


call_request_schema = CallRequestSchema()
call_dtmf_schema = CallDtmfSchema()
user_call_request_schema = UserCallRequestSchema()


class CallsResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('calld.calls.read')
    def get(self):
        application_filter = request.args.get('application')
        application_instance_filter = request.args.get('application_instance')

        calls = self.calls_service.list_calls(application_filter, application_instance_filter)

        return {
            'items': call_schema.dump(calls, many=True),
        }, 200

    @required_acl('calld.calls.create')
    def post(self):
        request_body = call_request_schema.load(request.get_json(force=True))

        call = self.calls_service.originate(request_body)

        return call_schema.dump(call), 201


class MyCallsResource(AuthResource):

    def __init__(self, auth_client, calls_service):
        self.auth_client = auth_client
        self.calls_service = calls_service

    @required_acl('calld.users.me.calls.read')
    def get(self):
        application_filter = request.args.get('application')
        application_instance_filter = request.args.get('application_instance')
        user_uuid = get_token_user_uuid_from_request(self.auth_client)

        calls = self.calls_service.list_calls_user(user_uuid, application_filter, application_instance_filter)

        return {
            'items': call_schema.dump(calls, many=True),
        }, 200

    @required_acl('calld.users.me.calls.create')
    def post(self):
        request_body = user_call_request_schema.load(request.get_json(force=True))

        user_uuid = get_token_user_uuid_from_request(self.auth_client)

        call = self.calls_service.originate_user(request_body, user_uuid)

        return call_schema.dump(call), 201


class CallResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('calld.calls.{call_id}.read')
    def get(self, call_id):
        call = self.calls_service.get(call_id)

        return call_schema.dump(call)

    @required_acl('calld.calls.{call_id}.delete')
    def delete(self, call_id):
        self.calls_service.hangup(call_id)

        return None, 204


class CallMuteStartResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('calld.calls.{call_id}.mute.start.update')
    def put(self, call_id):
        self.calls_service.mute(call_id)
        return '', 204


class CallMuteStopResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('calld.calls.{call_id}.mute.stop.update')
    def put(self, call_id):
        self.calls_service.unmute(call_id)
        return '', 204


class MyCallMuteStartResource(AuthResource):

    def __init__(self, auth_client, calls_service):
        self.auth_client = auth_client
        self.calls_service = calls_service

    @required_acl('calld.users.me.calls.{call_id}.mute.start.update')
    def put(self, call_id):
        user_uuid = get_token_user_uuid_from_request(self.auth_client)
        self.calls_service.mute_user(call_id, user_uuid)
        return '', 204


class MyCallMuteStopResource(AuthResource):

    def __init__(self, auth_client, calls_service):
        self.auth_client = auth_client
        self.calls_service = calls_service

    @required_acl('calld.users.me.calls.{call_id}.mute.stop.update')
    def put(self, call_id):
        user_uuid = get_token_user_uuid_from_request(self.auth_client)
        self.calls_service.unmute_user(call_id, user_uuid)
        return '', 204


class MyCallResource(AuthResource):

    def __init__(self, auth_client, calls_service):
        self.auth_client = auth_client
        self.calls_service = calls_service

    @required_acl('calld.users.me.calls.{call_id}.delete')
    def delete(self, call_id):
        user_uuid = get_token_user_uuid_from_request(self.auth_client)
        self.calls_service.hangup_user(call_id, user_uuid)

        return None, 204


class CallDtmfResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('calld.calls.{call_id}.dtmf.update')
    def put(self, call_id):
        request_args = call_dtmf_schema.load(request.args)
        self.calls_service.send_dtmf(call_id, request_args['digits'])
        return '', 204


class MyCallDtmfResource(AuthResource):

    def __init__(self, auth_client, calls_service):
        self.auth_client = auth_client
        self.calls_service = calls_service

    @required_acl('calld.users.me.calls.{call_id}.dtmf.update')
    def put(self, call_id):
        request_args = call_dtmf_schema.load(request.args)
        user_uuid = get_token_user_uuid_from_request(self.auth_client)
        self.calls_service.send_dtmf_user(call_id, user_uuid, request_args['digits'])
        return '', 204


class CallHoldResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('calld.calls.{call_id}.hold.start.update')
    def put(self, call_id):
        self.calls_service.hold(call_id)
        return '', 204


class CallUnholdResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('calld.calls.{call_id}.hold.stop.update')
    def put(self, call_id):
        self.calls_service.unhold(call_id)
        return '', 204


class MyCallHoldResource(AuthResource):

    def __init__(self, auth_client, calls_service):
        self.auth_client = auth_client
        self.calls_service = calls_service

    @required_acl('calld.users.me.calls.{call_id}.hold.start.update')
    def put(self, call_id):
        user_uuid = get_token_user_uuid_from_request(self.auth_client)
        self.calls_service.hold_user(call_id, user_uuid)
        return '', 204


class MyCallUnholdResource(AuthResource):

    def __init__(self, auth_client, calls_service):
        self.auth_client = auth_client
        self.calls_service = calls_service

    @required_acl('calld.users.me.calls.{call_id}.hold.stop.update')
    def put(self, call_id):
        user_uuid = get_token_user_uuid_from_request(self.auth_client)
        self.calls_service.unhold_user(call_id, user_uuid)
        return '', 204


class CallRecordStartResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('calld.calls.{call_id}.record.start.update')
    def put(self, call_id):
        self.calls_service.record_start(call_id)
        return '', 204


class CallRecordStopResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('calld.calls.{call_id}.record.stop.update')
    def put(self, call_id):
        self.calls_service.record_stop(call_id)
        return '', 204


class MyCallRecordStopResource(AuthResource):

    def __init__(self, auth_client, calls_service):
        self.auth_client = auth_client
        self.calls_service = calls_service

    @required_acl('calld.users.me.calls.{call_id}.record.stop.update')
    def put(self, call_id):
        user_uuid = get_token_user_uuid_from_request(self.auth_client)
        self.calls_service.record_stop_user(call_id, user_uuid)
        return '', 204


class MyCallRecordStartResource(AuthResource):

    def __init__(self, auth_client, calls_service):
        self.auth_client = auth_client
        self.calls_service = calls_service

    @required_acl('calld.users.me.calls.{call_id}.record.start.update')
    def put(self, call_id):
        user_uuid = get_token_user_uuid_from_request(self.auth_client)
        self.calls_service.record_start_user(call_id, user_uuid)
        return '', 204


class CallAnswerResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('calld.calls.{call_id}.answer.update')
    def put(self, call_id):
        self.calls_service.answer(call_id)
        return '', 204


class MyCallAnswerResource(AuthResource):

    def __init__(self, auth_client, calls_service):
        self.auth_client = auth_client
        self.calls_service = calls_service

    @required_acl('calld.users.me.calls.{call_id}.answer.update')
    def put(self, call_id):
        user_uuid = get_token_user_uuid_from_request(self.auth_client)
        self.calls_service.answer_user(call_id, user_uuid)
        return '', 204


class ConnectCallToUserResource(AuthResource):

    def __init__(self, calls_service):
        self.calls_service = calls_service

    @required_acl('calld.calls.{call_id}.user.{user_uuid}.update')
    def put(self, call_id, user_uuid):
        new_call_id = self.calls_service.connect_user(call_id, user_uuid)
        new_call = self.calls_service.get(new_call_id)

        return call_schema.dump(new_call)
