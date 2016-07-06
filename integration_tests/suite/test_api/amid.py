# -*- coding: utf-8 -*-
# Copyright (C) 2015-2016 Avencall
# SPDX-License-Identifier: GPL-3.0+

import requests


class AmidClient(object):

    def set_action_result(self, result):
        url = u'https://localhost:9491/_set_action'
        requests.post(url, json=result, verify=False)

    def set_no_valid_exten(self):
        result = []
        self.set_action_result(result)

    def set_valid_exten(self, context, exten, priority='1'):
        result = [
            {'Event': 'ListDialplan',
             'Context': context,
             'Exten': exten,
             'Priority': priority}
        ]
        self.set_action_result(result)

    def reset(self):
        self.set_action_result('')
