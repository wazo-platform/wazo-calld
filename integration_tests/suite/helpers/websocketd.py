# Copyright 2017 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0-or-later

import requests


class WebsocketdClient:

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def url(self, *parts):
        return 'http://{host}:{port}/{path}'.format(host=self.host,
                                                    port=self.port,
                                                    path='/'.join(parts))

    def set_get_presence(self, code=0, presence='available'):
        url = self.url('_set_response')
        body = {'response': 'get_presence',
                'content': {'op': 'get_presence', 'code': code, 'msg': {'presence': presence}}}
        requests.post(url, json=body)

    def set_set_presence(self, code=0):
        url = self.url('_set_response')
        body = {'response': 'set_presence',
                'content': {'op': 'set_presence', 'code': code}}
        requests.post(url, json=body)

    def reset(self):
        url = self.url('_reset')
        requests.post(url)

    def requests(self):
        url = self.url('_requests')
        return requests.get(url).json()

    def websockets(self):
        url = self.url('_websockets')
        return requests.get(url).json()
