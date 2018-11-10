# Copyright 2016-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import requests


class ChanTest(object):

    def __init__(self, ari_config):
        self.config = ari_config
        self._auth = (self.config['username'], self.config['password'])

    def answer_channel(self, channel_id):
        url = '{base}/ari/chan_test/answer'.format(base=self.config['base_url'])
        params = {'id': channel_id}
        response = requests.post(url, params=params, auth=self._auth)
        response.raise_for_status()

    def send_dtmf(self, channel_id, digit):
        assert len(digit) == 1, 'Only a single digit at a time is supported'
        url = '{base}/ari/chan_test/dtmf'.format(base=self.config['base_url'])
        params = {'id': channel_id, 'digit': digit}
        response = requests.post(url, params=params, auth=self._auth)
        response.raise_for_status()
