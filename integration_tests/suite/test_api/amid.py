# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import requests


class AmidClient(object):

    def __init__(self, host, port):
        self.host = host
        self.port = port

    def url(self, *parts):
        return 'https://{host}:{port}/{path}'.format(host=self.host,
                                                     port=self.port,
                                                     path='/'.join(parts))

    def set_action_result(self, result):
        requests.post(self.url('_set_action'), json=result, verify=False)

    def set_no_valid_exten(self):
        result = []
        self.set_action_result(result)

    def set_valid_exten(self, context, exten, priority='1'):
        result = [
            {'Event': 'ListDialplan',
             'Context': context,
             'Exten': exten,
             'Priority': str(priority)}
        ]
        self.set_action_result(result)

    def reset(self):
        url = self.url('_reset')
        requests.post(url, verify=False)

    def requests(self):
        url = self.url('_requests')
        return requests.get(url, verify=False).json()
