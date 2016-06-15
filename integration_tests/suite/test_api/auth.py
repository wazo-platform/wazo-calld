# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import requests


class AuthClient(object):

    def set_token(self, token):
        url = 'https://localhost:9497/_set_token'
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
