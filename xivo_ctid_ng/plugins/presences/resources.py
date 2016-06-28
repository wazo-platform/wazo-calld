# -*- coding: utf-8 -*-
# Copyright (C) 2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

from flask import request
from marshmallow import Schema, fields

from xivo_ctid_ng.core.auth import required_acl
from xivo_ctid_ng.core.auth import get_token_user_uuid_from_request
from xivo_ctid_ng.core.rest_api import AuthResource


class PresenceRequestSchema(Schema):

    presence = fields.Str(required=True)

presence_request_schema = PresenceRequestSchema(strict=True)


def presence_body(xivo_uuid, user_uuid, presence):
    return {'xivo_uuid': xivo_uuid,
            'user_uuid': user_uuid,
            'presence': presence}


class PresencesResource(AuthResource):

    def __init__(self, presences_service):
        self._presences_service = presences_service

    @required_acl('ctid-ng.users.{user_uuid}.presences.read')
    def get(self, user_uuid):
        xivo_uuid, status = self._presences_service.get_presence(user_uuid)

        return presence_body(xivo_uuid, user_uuid, status), 200

    @required_acl('ctid-ng.users.{user_uuid}.presences.update')
    def put(self, user_uuid):
        request_body = presence_request_schema.load(request.get_json(force=True)).data

        self._presences_service.update_presence(user_uuid, request_body['presence'])

        return '', 204


class UserPresencesResource(AuthResource):

    def __init__(self, auth_client, presences_service):
        self._auth_client = auth_client
        self._presences_service = presences_service

    @required_acl('ctid-ng.users.me.presences.read')
    def get(self):
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        xivo_uuid, status = self._presences_service.get_presence(user_uuid)

        return presence_body(xivo_uuid, user_uuid, status), 200

    @required_acl('ctid-ng.users.me.presences.update')
    def put(self):
        request_body = presence_request_schema.load(request.get_json(force=True)).data

        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        self._presences_service.update_presence(user_uuid, request_body['presence'])

        return '', 204
