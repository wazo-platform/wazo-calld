# Copyright 2026 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import requests


class CallLogdClient:
    def __init__(self, host, port):
        self._host = host
        self._port = port

    def url(self, *parts):
        return f'http://{self._host}:{self._port}/1.0/{"/".join(parts)}'

    def is_up(self):
        try:
            response = requests.get(self.url('_status'))
            return response.status_code == 200
        except requests.RequestException:
            return False

    def set_transcriptions(self, transcriptions):
        url = self.url('_set_transcriptions')
        body = {'transcriptions': transcriptions}
        response = requests.post(url, json=body)
        response.raise_for_status()

    def reset(self):
        url = self.url('_reset')
        response = requests.post(url)
        response.raise_for_status()
