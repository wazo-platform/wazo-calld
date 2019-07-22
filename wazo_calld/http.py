# Copyright 2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from ari.exceptions import (
    ARIException,
    ARIHTTPError,
)

from flask_restful import Resource
from functools import wraps

from xivo import (
    mallow_helpers,
    rest_api_helpers,
)
from xivo.auth_verifier import AuthVerifier

from .exceptions import (
    AsteriskARIError,
    AsteriskARIUnreachable,
)

auth_verifier = AuthVerifier()


def handle_ari_exception(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ARIHTTPError as e:
            raise AsteriskARIError({'base_url': e.client.base_url}, e.original_error)
        except ARIException as e:
            raise AsteriskARIUnreachable({'base_url': e.client.base_url}, e.original_error)
    return wrapper


class ErrorCatchingResource(Resource):
    method_decorators = ([mallow_helpers.handle_validation_exception,
                          handle_ari_exception,
                          rest_api_helpers.handle_api_exception] + Resource.method_decorators)


class AuthResource(ErrorCatchingResource):
    method_decorators = [auth_verifier.verify_token] + ErrorCatchingResource.method_decorators
