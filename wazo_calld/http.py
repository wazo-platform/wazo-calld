# Copyright 2019-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from functools import wraps

from ari.exceptions import ARIException, ARIHTTPError
from flask_restful import Resource
from xivo import mallow_helpers, rest_api_helpers
from xivo.flask.auth_verifier import AuthVerifierFlask

from .exceptions import AsteriskARIError, AsteriskARIUnreachable

auth_verifier = AuthVerifierFlask()


def handle_ari_exception(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ARIHTTPError as e:
            raise AsteriskARIError(
                {'base_url': e.client.base_url}, e.original_error, e.original_message
            )
        except ARIException as e:
            raise AsteriskARIUnreachable(
                {'base_url': e.client.base_url}, e.original_error, e.original_message
            )

    return wrapper


class ErrorCatchingResource(Resource):
    method_decorators = [
        mallow_helpers.handle_validation_exception,
        handle_ari_exception,
        rest_api_helpers.handle_api_exception,
    ] + Resource.method_decorators


class AuthResource(ErrorCatchingResource):
    method_decorators = [
        auth_verifier.verify_tenant,
        auth_verifier.verify_token,
    ] + ErrorCatchingResource.method_decorators
