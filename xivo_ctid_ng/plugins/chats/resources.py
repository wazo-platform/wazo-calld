# -*- coding: utf-8 -*-
# Copyright 2016-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from flask import request
from marshmallow import Schema, fields
from marshmallow.validate import Range

from xivo_ctid_ng.core.auth import required_acl
from xivo_ctid_ng.core.auth import get_token_user_uuid_from_request
from xivo_ctid_ng.core.rest_api import AuthResource


class UserChatRequestSchema(Schema):

    to = fields.UUID(required=True)
    to_xivo_uuid = fields.UUID()
    alias = fields.Str(required=True)
    msg = fields.Str(required=True)


class ChatRequestSchema(UserChatRequestSchema):

    from_ = fields.UUID(attribute='from', load_from='from', required=True)

user_chat_request_schema = UserChatRequestSchema(strict=True)
chat_request_schema = ChatRequestSchema(strict=True)


class UserChatListRequestSchema(Schema):
    participant_user_uuid = fields.UUID()
    participant_server_uuid = fields.UUID()
    limit = fields.Integer(validate=Range(min=0), missing=100)

    class Meta(object):
        strict = True


class UserChatSchema(Schema):
    date = fields.DateTime()
    source_user_uuid = fields.UUID()
    source_server_uuid = fields.UUID()
    destination_user_uuid = fields.UUID()
    destination_server_uuid = fields.UUID()
    msg = fields.String()
    direction = fields.String()


class UserChatListSchema(Schema):
    items = fields.Nested(UserChatSchema, many=True)


class ChatsResource(AuthResource):

    def __init__(self, chats_service):
        self._chats_service = chats_service

    @required_acl('ctid-ng.chats.create')
    def post(self):
        request_body = chat_request_schema.load(request.get_json(force=True)).data

        self._chats_service.send_message(request_body)

        return '', 204


class UserChatsResource(AuthResource):

    def __init__(self, auth_client, chats_service):
        self._auth_client = auth_client
        self._chats_service = chats_service

    @required_acl('ctid-ng.users.me.chats.create')
    def post(self):
        request_body = user_chat_request_schema.load(request.get_json(force=True)).data

        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        self._chats_service.send_message(request_body, user_uuid)

        return '', 204

    @required_acl('ctid-ng.users.me.chats.read')
    def get(self):
        args = UserChatListRequestSchema().load(request.args).data
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        history = self._chats_service.get_history(user_uuid, args)
        return UserChatListSchema().dump(history).data
