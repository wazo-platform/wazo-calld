# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import requests


class AuthClient(object):

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


class MockUserToken(object):

    def __init__(self, token, user_uuid):
        self._token = token
        self._auth_id = user_uuid

    def to_dict(self):
        return {
            'token': self._token,
            'auth_id': self._auth_id,
        }
