# Copyright 2020-2022 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests


class PhonedClient:

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def url(self, *parts):
        return 'http://{host}:{port}/{path}'.format(
            host=self.host,
            port=self.port,
            path='/'.join(parts)
        )

    def reset(self):
        url = self.url('_reset')
        response = requests.post(url)
        response.raise_for_status()

    def requests(self):
        url = self.url('_requests')
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
