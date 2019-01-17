# Copyright 2015-2019 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests


class AmidClient:

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def url(self, *parts):
        return 'https://{host}:{port}/{path}'.format(host=self.host,
                                                     port=self.port,
                                                     path='/'.join(parts))

    def is_up(self):
        url = self.url()
        try:
            response = requests.get(url, verify=False)
            return response.status_code == 404
        except requests.RequestException:
            return False

    def set_action_result(self, result):
        requests.post(self.url('_set_action'), json=result, verify=False)

    def set_no_valid_exten(self):
        result = []
        self.set_action_result(result)

    def set_valid_exten(self, context, exten, priority='1'):
        body = {'context': context, 'exten': exten, 'priority': priority}
        requests.post(self.url('_set_valid_exten'), json=body, verify=False)

    def reset(self):
        url = self.url('_reset')
        requests.post(url, verify=False)

    def requests(self):
        url = self.url('_requests')
        return requests.get(url, verify=False).json()
