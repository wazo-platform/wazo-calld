# Copyright 2015-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from typing import TYPE_CHECKING

from requests import HTTPError
from werkzeug.local import LocalProxy as Proxy
from xivo import auth_verifier
from xivo.auth_verifier import required_tenant

from wazo_calld.exceptions import (
    MasterTenantNotInitialized,
    TokenWithUserUUIDRequiredError,
)
from wazo_calld.http_server import app

if TYPE_CHECKING:
    from flask import request as _request
    from xivo.auth_verifier import Request

    request: Request = _request  # type: ignore[assignment]
else:
    from flask import request


logger = logging.getLogger(__name__)
required_acl = auth_verifier.required_acl
extract_token_id_from_query_or_header = (
    auth_verifier.extract_token_id_from_query_or_header
)
Unauthorized = auth_verifier.Unauthorized


def get_token_user_uuid_from_request():
    try:
        user_uuid = request.user_uuid
    except HTTPError as e:
        logger.warning('HTTP error from wazo-auth while getting token: %s', e)
        raise TokenWithUserUUIDRequiredError()

    if not user_uuid:
        raise TokenWithUserUUIDRequiredError()
    return user_uuid


def required_master_tenant():
    return required_tenant(master_tenant_uuid)


def init_master_tenant(token):
    tenant_uuid = token['metadata']['tenant_uuid']
    app.config['auth']['master_tenant_uuid'] = tenant_uuid
    logger.debug('Initiated master tenant UUID: %s', tenant_uuid)


def get_master_tenant_uuid():
    if not app:
        raise Exception('Flask application not configured')

    tenant_uuid = app.config['auth'].get('master_tenant_uuid')
    if not tenant_uuid:
        raise MasterTenantNotInitialized()
    return tenant_uuid


master_tenant_uuid = Proxy(get_master_tenant_uuid)
