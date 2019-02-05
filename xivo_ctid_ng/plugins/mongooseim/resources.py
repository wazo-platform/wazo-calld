# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from flask import request
from flask import make_response
from marshmallow import Schema, fields
from requests import HTTPError

from xivo_ctid_ng.auth import Unauthorized
from xivo_ctid_ng.rest_api import ErrorCatchingResource


class BaseSchema(Schema):
    class Meta:
        strict = True


class MessageRequestSchema(BaseSchema):

    author = fields.String(required=True)
    server = fields.String()
    receiver = fields.String(required=True)
    message = fields.String(required=True)


class MessageCallbackResource(ErrorCatchingResource):

    def __init__(self, message_callback_service):
        self._message_callback_service = message_callback_service

    def post(self):
        request_body = MessageRequestSchema().load(request.form).data
        self._message_callback_service.send_message(request_body)
        return '', 204


class PresenceRequestSchema(BaseSchema):

    user = fields.String(required=True)
    server = fields.String(required=True)
    resource = fields.String()
    status = fields.String(required=True)


class PresenceCallbackResource(ErrorCatchingResource):

    def __init__(self, presence_callback_service):
        self._presence_callback_service = presence_callback_service

    def post(self):
        request_body = PresenceRequestSchema().load(request.get_json()).data
        self._presence_callback_service.send_message(request_body)
        return '', 204


def output_plain(data, code, http_headers=None):
    response = make_response(data, code)
    response.headers.extend(http_headers or {})
    return response


class MongooseIMUserSchema(BaseSchema):

    user = fields.String(required=True)
    server = fields.String()
    token = fields.String(required=True, load_from='pass')


def extract_token_id_from_mongooseim_format():
    user = MongooseIMUserSchema().load(request.args).data
    return user['token']


class CheckPasswordResource(ErrorCatchingResource):

    def __init__(self, auth_client):
        self._auth_client = auth_client

    def get(self):
        token_id = extract_token_id_from_mongooseim_format()
        try:
            self._check_admin_authorization(token_id)
        except Unauthorized:
            self._check_user_authorization(token_id)

        return output_plain('true', 200)

    def _check_admin_authorization(self, token_id):
        if not self._auth_client.token.is_valid(token_id, required_acl='mongooseim.admin'):
            raise Unauthorized(token_id)

    def _check_user_authorization(self, token_id):
        user = MongooseIMUserSchema().load(request.args).data

        try:
            token = self._auth_client.token.get(token_id, required_acl='websocketd')
        except HTTPError:
            raise Unauthorized(token_id)

        if user['user'] != token['xivo_user_uuid']:
            raise Unauthorized(token_id)


class UserExistsResource(ErrorCatchingResource):

    def get(self):
        return output_plain('true', 200)
