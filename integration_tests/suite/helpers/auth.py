# Copyright 2013-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests


class AuthClient:

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def url(self, *parts):
        return 'http://{host}:{port}/{path}'.format(
            host=self.host,
            port=self.port,
            path='/'.join(parts)
        )

    def set_token(self, token):
        url = self.url('_set_token')
        response = requests.post(url, json=token.to_dict())
        response.raise_for_status()

    def set_refresh_tokens(self, refresh_tokens):
        url = self.url('_set_refresh_tokens')
        response = requests.post(url, json=refresh_tokens)
        response.raise_for_status()


class MockUserToken:

    def __init__(self, token, user_uuid, acl=None, tenant_uuid=None):
        self._token = token
        self._user_uuid = user_uuid
        self._acl = acl
        self._tenant_uuid = tenant_uuid

    def to_dict(self):
        result = {
            'token': self._token,
            'auth_id': self._user_uuid,
            'metadata': {},
        }
        if self._acl:
            result['acl'] = self._acl
        if self._tenant_uuid:
            result['metadata']['tenant_uuid'] = self._tenant_uuid
        if self._user_uuid:
            result['metadata']['uuid'] = self._user_uuid
        return result
