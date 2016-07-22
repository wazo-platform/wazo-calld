# -*- coding: utf-8 -*-

# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import requests


class ChanTest(object):
    def __init__(self, ari_config):
        self.config = ari_config

    def answer_channel(self, channel):
        url = '{base}/ari/chan_test/answer'.format(base=self.config['base_url'])
        params = {'id': channel.id}
        response = requests.post(url, params=params, auth=(self.config['username'], self.config['password']))
        response.raise_for_status()
