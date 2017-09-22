# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from flask import request
from flask import make_response
from marshmallow import Schema, fields

from xivo_ctid_ng.rest_api import ErrorCatchingResource


class MessageRequestSchema(Schema):

    author = fields.String(required=True)
    server = fields.String()
    receiver = fields.String(required=True)
    message = fields.String(required=True)

    class Meta:
        strict = True


class MessageCallbackResource(ErrorCatchingResource):

    def __init__(self, message_callback_service):
        self._message_callback_service = message_callback_service

    def post(self):
        request_body = MessageRequestSchema().load(request.form).data
        self._message_callback_service.send_message(request_body)
        return '', 204


def output_plain(data, code, http_headers=None):
    response = make_response(data, code)
    response.headers.extend(http_headers or {})
    return response


class CheckPasswordResource(ErrorCatchingResource):

    def get(self):
        return output_plain('false', 401)


class UserExistsResource(ErrorCatchingResource):

    def get(self):
        return output_plain('true', 200)
