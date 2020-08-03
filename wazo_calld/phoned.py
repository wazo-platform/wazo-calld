# Copyright 2020 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests


class PhonedClient:

    def __init__(self, config):
        self.config = config.get('phoned', {})
        self.token = None

    def set_token(self, token):
        self.token = token

    def hold_endpoint(self, endpoint_name):
        url = '{}:{}/endoints/{}/hold/start'.format(self.config['host'])
        headers = {'X-Auth-Token': self.token}
        result = requests.get(url, headers=headers)
        result.raise_for_status()

    def unhold_endpoint(self, endpoint_name):
        url = '{}/endoints/{}/hold/start'
        headers = {'X-Auth-Token': self.token}
        result = requests.get(url, headers=headers)
        result.raise_for_status()
