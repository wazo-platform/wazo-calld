# -*- coding: utf-8 -*-
# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from flask import request

from xivo_ctid_ng.auth import get_token_user_uuid_from_request
from xivo_ctid_ng.auth import required_acl
from xivo_ctid_ng.rest_api import AuthResource

from .schema import (
    relocate_schema,
    user_relocate_request_schema,
)


class UserRelocatesResource(AuthResource):

    def __init__(self, auth_client, relocates_service):
        self._auth_client = auth_client
        self._relocates_service = relocates_service

    @required_acl('ctid-ng.users.me.relocates.read')
    def get(self):
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        relocates = self._relocates_service.list_from_user(user_uuid)

        return {
            'items': relocate_schema.dump(relocates, many=True).data
        }, 200

    @required_acl('ctid-ng.users.me.relocates.create')
    def post(self):
        request_body = user_relocate_request_schema.load(request.get_json(force=True)).data
        user_uuid = get_token_user_uuid_from_request(self._auth_client)
        relocate = self._relocates_service.create_from_user(request_body['initiator_call'],
                                                            request_body['destination'],
                                                            request_body['location'],
                                                            user_uuid)
        result = relocate_schema.dump(relocate).data
        return result, 201
