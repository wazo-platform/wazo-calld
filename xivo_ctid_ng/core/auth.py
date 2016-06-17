# -*- coding: utf-8 -*-
# Copyright 2015-2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from flask import request
from xivo import auth_verifier

from xivo_ctid_ng.core.exceptions import TokenWithUserUUIDRequiredError

required_acl = auth_verifier.required_acl


def get_token_user_uuid_from_request(auth_client):
    token = request.headers['X-Auth-Token']
    token_infos = auth_client.token.get(token)
    user_uuid = token_infos['xivo_user_uuid']
    if not user_uuid:
        raise TokenWithUserUUIDRequiredError()
    return user_uuid
