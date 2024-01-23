# Copyright 2015-2024 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests
from wazo_amid_client import Client as _AmidClient


class AmidClient(_AmidClient):
    def is_up(self):
        try:
            self.status()
        except requests.HTTPError:
            return True
        except requests.RequestException:
            return False
        return True


class MockAmidClient:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def url(self, *parts):
        return f'http://{self.host}:{self.port}/{"/".join(parts)}'

    def is_up(self):
        url = self.url()
        try:
            response = requests.get(url)
            return response.status_code == 404
        except requests.RequestException:
            return False

    def set_action_result(self, result):
        response = requests.post(self.url('_set_action'), json=result)
        response.raise_for_status()

    def set_no_valid_exten(self):
        result = []
        self.set_action_result(result)

    def set_valid_exten(self, context, exten, priority='1'):
        body = {'context': context, 'exten': exten, 'priority': priority}
        response = requests.post(self.url('_set_valid_exten'), json=body)
        response.raise_for_status()

    def reset(self):
        url = self.url('_reset')
        response = requests.post(url)
        response.raise_for_status()

    def requests(self):
        url = self.url('_requests')
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
