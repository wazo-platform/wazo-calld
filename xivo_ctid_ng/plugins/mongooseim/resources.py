# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from flask import request
from flask import make_response
from marshmallow import Schema, fields

from xivo_ctid_ng.auth import required_acl
from xivo_ctid_ng.rest_api import AuthResource, ErrorCatchingResource


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
    user = fields.String()
    server = fields.String()
    token = fields.String(required=True, load_from='pass')


def extract_token_id_from_mongooseim_format():
    user = MongooseIMUserSchema().load(request.args).data
    return user['token']


class CheckPasswordResource(AuthResource):

    @required_acl('ctid-ng.users.me.chats.create', extract_token_id=extract_token_id_from_mongooseim_format)
    def get(self):
        return output_plain('true', 200)


class UserExistsResource(ErrorCatchingResource):

    def get(self):
        return output_plain('true', 200)
