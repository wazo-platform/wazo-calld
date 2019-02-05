# Copyright 2013-2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests


class AuthClient:

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def url(self, *parts):
        return 'https://{host}:{port}/{path}'.format(host=self.host,
                                                     port=self.port,
                                                     path='/'.join(parts))

    def set_token(self, token):
        url = self.url('_set_token')
        requests.post(url, json=token.to_dict(), verify=False)


class MockUserToken:

    def __init__(self, token, user_uuid, acls=None):
        self._token = token
        self._auth_id = user_uuid
        self._acls = acls

    def to_dict(self):
        result = {'token': self._token,
                  'auth_id': self._auth_id}
        if self._acls:
            result['acls'] = self._acls
        return result
