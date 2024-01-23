# Copyright 2017-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from flask import request

from wazo_calld.auth import get_token_user_uuid_from_request, required_acl
from wazo_calld.http import AuthResource

from .schemas import relocate_schema, user_relocate_request_schema


class UserRelocatesResource(AuthResource):
    def __init__(self, relocates_service):
        self._relocates_service = relocates_service

    @required_acl('calld.users.me.relocates.read')
    def get(self):
        user_uuid = get_token_user_uuid_from_request()
        relocates = self._relocates_service.list_from_user(user_uuid)

        return {'items': relocate_schema.dump(relocates, many=True)}, 200

    @required_acl('calld.users.me.relocates.create')
    def post(self):
        request_body = user_relocate_request_schema.load(request.get_json(force=True))
        user_uuid = get_token_user_uuid_from_request()
        relocate = self._relocates_service.create_from_user(
            request_body['initiator_call'],
            request_body['destination'],
            request_body['location'],
            request_body['completions'],
            request_body['timeout'],
            request_body['auto_answer'],
            user_uuid,
        )
        result = relocate_schema.dump(relocate)
        return result, 201


class UserRelocateResource(AuthResource):
    def __init__(self, relocates_service):
        self._relocates_service = relocates_service

    @required_acl('calld.users.me.relocates.{relocate_uuid}.read')
    def get(self, relocate_uuid):
        user_uuid = get_token_user_uuid_from_request()
        relocate = self._relocates_service.get_from_user(relocate_uuid, user_uuid)

        result = relocate_schema.dump(relocate)
        return result, 200


class UserRelocateCompleteResource(AuthResource):
    def __init__(self, relocates_service):
        self._relocates_service = relocates_service

    @required_acl('calld.users.me.relocates.{relocate_uuid}.complete.update')
    def put(self, relocate_uuid):
        user_uuid = get_token_user_uuid_from_request()
        self._relocates_service.complete_from_user(relocate_uuid, user_uuid)
        return '', 204


class UserRelocateCancelResource(AuthResource):
    def __init__(self, relocates_service):
        self._relocates_service = relocates_service

    @required_acl('calld.users.me.relocates.{relocate_uuid}.cancel.update')
    def put(self, relocate_uuid):
        user_uuid = get_token_user_uuid_from_request()
        self._relocates_service.cancel_from_user(relocate_uuid, user_uuid)
        return '', 204
