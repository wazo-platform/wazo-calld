# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests

from .exceptions import PhonedError


class PhonedClient:

    def __init__(self, **config):
        self.config = config
        self.token = None

    def set_token(self, token):
        self.token = token

    def hold_endpoint(self, endpoint_name):
        url = 'http://{}:{}/0.1/endpoints/{}/hold/start'.format(self.config['host'], self.config['port'], endpoint_name)
        headers = {'X-Auth-Token': self.token}
        result = requests.put(url, headers=headers)
        try:
            result.raise_for_status()
        except requests.HTTPError as e:
            raise PhonedError(self.config, e)

    def unhold_endpoint(self, endpoint_name):
        url = 'http://{}:{}/0.1/endpoints/{}/hold/stop'.format(self.config['host'], self.config['port'], endpoint_name)
        headers = {'X-Auth-Token': self.token}
        result = requests.put(url, headers=headers)
        try:
            result.raise_for_status()
        except requests.HTTPError as e:
            raise PhonedError(self.config, e)

    def answer_endpoint(self, endpoint_name):
        url = 'http://{}:{}/0.1/endpoints/{}/answer'.format(self.config['host'], self.config['port'], endpoint_name)
        headers = {'X-Auth-Token': self.token}
        result = requests.put(url, headers=headers)
        try:
            result.raise_for_status()
        except requests.HTTPError as e:
            raise PhonedError(self.config, e)
